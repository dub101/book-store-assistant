from collections.abc import Callable
from pathlib import Path

from book_store_assistant.config import AppConfig
from book_store_assistant.pipeline.input import read_isbn_inputs
from book_store_assistant.pipeline.process_results import ProcessResult
from book_store_assistant.publisher_identity.service import resolve_publisher_identity
from book_store_assistant.resolution.providers import (
    build_default_bibliographic_extractor,
    build_default_record_quality_validator,
)
from book_store_assistant.resolution.service import resolve_all
from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.diagnostics import changed_record_fields, with_diagnostic
from book_store_assistant.sources.publisher_discovery import (
    augment_fetch_results_with_publisher_discovery,
)
from book_store_assistant.sources.publisher_pages import (
    augment_fetch_results_with_publisher_pages,
)
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.retailer_pages import (
    augment_fetch_results_with_retailer_editorials,
)
from book_store_assistant.sources.service import (
    FetchCompleteCallback,
    FetchStartCallback,
    fetch_all,
)
from book_store_assistant.sources.source_pages import (
    augment_fetch_results_with_source_pages,
)
from book_store_assistant.sources.staged import fetch_with_stages
from book_store_assistant.sources.web_search import (
    augment_fetch_results_with_editorial_search,
)

StatusUpdateCallback = Callable[[str], None]


def _needs_bibliographic_completion(result: FetchResult) -> bool:
    if result.record is None:
        return True
    return not (
        bool((result.record.title or "").strip())
        and bool((result.record.author or "").strip())
        and bool((result.record.editorial or "").strip())
    )


def _has_editorial_signal(result: FetchResult) -> bool:
    return (
        result.record is not None
        and bool((result.record.editorial or "").strip())
    )


def _incomplete_isbns(fetch_results: list[FetchResult]) -> set[str]:
    return {
        result.isbn
        for result in fetch_results
        if _needs_bibliographic_completion(result)
    }


def _publisher_target_isbns(fetch_results: list[FetchResult]) -> set[str]:
    return {
        result.isbn
        for result in fetch_results
        if _needs_bibliographic_completion(result) and _has_editorial_signal(result)
    }


def _annotate_stage_updates(
    previous_results: list[FetchResult],
    current_results: list[FetchResult],
    stage_name: str,
) -> list[FetchResult]:
    previous_by_isbn = {result.isbn: result for result in previous_results}
    annotated_results: list[FetchResult] = []

    for result in current_results:
        previous = previous_by_isbn.get(result.isbn)
        previous_record = previous.record if previous is not None else None
        changed_fields = changed_record_fields(previous_record, result.record)
        if not changed_fields:
            annotated_results.append(result)
            continue

        prior_update_exists = any(
            diagnostic.get("action") == "record_updated"
            for diagnostic in result.diagnostics
        )
        annotated_results.append(
            with_diagnostic(
                result,
                stage_name,
                "record_updated",
                changed_fields=changed_fields,
                previous_source=(
                    previous_record.source_name if previous_record is not None else None
                ),
                current_source=(result.record.source_name if result.record is not None else None),
                first_material_gain=not prior_update_exists,
            )
        )

    return annotated_results


def _run_augmented_stage(
    fetch_results: list[FetchResult],
    stage_name: str,
    runner: Callable[[list[FetchResult]], list[FetchResult]],
) -> list[FetchResult]:
    previous_results = [result.model_copy(deep=True) for result in fetch_results]
    current_results = runner(fetch_results)
    return _annotate_stage_updates(previous_results, current_results, stage_name)


def process_isbn_file(
    input_path: Path,
    source: MetadataSource | None = None,
    config: AppConfig | None = None,
    on_fetch_start: FetchStartCallback | None = None,
    on_fetch_complete: FetchCompleteCallback | None = None,
    on_status_update: StatusUpdateCallback | None = None,
) -> ProcessResult:
    """Read ISBNs, fetch bibliographic metadata, and resolve upload records."""
    app_config = config or AppConfig()
    input_result = read_isbn_inputs(input_path)
    validator = build_default_record_quality_validator(app_config)
    extractor = build_default_bibliographic_extractor(app_config)
    if source is None:
        fetch_results = fetch_with_stages(
            input_path,
            input_result.valid_inputs,
            app_config,
            on_fetch_start=on_fetch_start,
            on_fetch_complete=on_fetch_complete,
            on_stage_update=on_status_update,
        )
    else:
        active_source = source
        fetch_results = fetch_all(
            active_source,
            input_result.valid_inputs,
            on_fetch_start=on_fetch_start,
            on_fetch_complete=on_fetch_complete,
        )
    fetch_results = _run_augmented_stage(
        fetch_results,
        "source_pages",
        lambda current_results: augment_fetch_results_with_source_pages(
            current_results,
            timeout_seconds=app_config.web_search_timeout_seconds,
            on_status_update=on_status_update,
            max_retries=app_config.web_search_max_retries,
            backoff_seconds=app_config.web_search_backoff_seconds,
        ),
    )
    if app_config.web_search_fallback_enabled:
        fetch_results = _run_augmented_stage(
            fetch_results,
            "web_search_editorial",
            lambda current_results: augment_fetch_results_with_editorial_search(
                current_results,
                timeout_seconds=app_config.web_search_timeout_seconds,
                extractor=extractor,
                on_status_update=on_status_update,
                max_retries=app_config.web_search_max_retries,
                backoff_seconds=app_config.web_search_backoff_seconds,
                max_pages_per_record=app_config.web_search_max_pages_per_record,
                max_search_attempts_per_record=(
                    app_config.web_search_max_search_attempts_per_record
                ),
                max_fetch_attempts_per_record=(
                    app_config.web_search_max_fetch_attempts_per_record
                ),
            ),
        )
    publisher_target_isbns = _publisher_target_isbns(fetch_results)
    if app_config.publisher_page_lookup_enabled and publisher_target_isbns:
        fetch_results = _run_augmented_stage(
            fetch_results,
            "publisher_pages",
            lambda current_results: augment_fetch_results_with_publisher_pages(
                current_results,
                timeout_seconds=app_config.publisher_page_timeout_seconds,
                on_status_update=on_status_update,
                max_retries=app_config.publisher_page_max_retries,
                backoff_seconds=app_config.publisher_page_backoff_seconds,
                eligible_isbns=publisher_target_isbns,
                max_profiles_per_record=app_config.publisher_page_max_profiles_per_record,
                max_search_attempts_per_record=(
                    app_config.publisher_page_max_search_attempts_per_record
                ),
                max_fetch_attempts_per_record=(
                    app_config.publisher_page_max_fetch_attempts_per_record
                ),
            ),
        )
    if app_config.retailer_page_lookup_enabled and _incomplete_isbns(fetch_results):
        fetch_results = _run_augmented_stage(
            fetch_results,
            "retailer_lookup",
            lambda current_results: augment_fetch_results_with_retailer_editorials(
                current_results,
                timeout_seconds=app_config.retailer_page_timeout_seconds,
                on_status_update=on_status_update,
                max_retries=app_config.retailer_page_max_retries,
                backoff_seconds=app_config.retailer_page_backoff_seconds,
                max_search_attempts_per_record=(
                    app_config.retailer_page_max_search_attempts_per_record
                ),
                max_fetch_attempts_per_record=(
                    app_config.retailer_page_max_fetch_attempts_per_record
                ),
            ),
        )
    if app_config.publisher_page_lookup_enabled and _incomplete_isbns(fetch_results):
        fetch_results = _run_augmented_stage(
            fetch_results,
            "publisher_discovery",
            lambda current_results: augment_fetch_results_with_publisher_discovery(
                current_results,
                timeout_seconds=app_config.publisher_page_timeout_seconds,
                on_status_update=on_status_update,
                max_retries=app_config.publisher_page_max_retries,
                backoff_seconds=app_config.publisher_page_backoff_seconds,
                max_search_attempts_per_record=(
                    app_config.publisher_page_max_search_attempts_per_record
                ),
                max_fetch_attempts_per_record=(
                    app_config.publisher_page_max_fetch_attempts_per_record
                ),
            ),
        )
    fetch_results = [
        fetch_result.model_copy(
            update={"publisher_identity": resolve_publisher_identity(fetch_result)}
        )
        for fetch_result in fetch_results
    ]
    resolution_results = resolve_all(fetch_results, validator=validator)

    return ProcessResult(
        input_result=input_result,
        fetch_results=fetch_results,
        resolution_results=resolution_results,
    )
