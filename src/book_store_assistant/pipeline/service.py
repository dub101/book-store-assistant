from collections.abc import Callable
from pathlib import Path

from book_store_assistant.config import AppConfig
from book_store_assistant.pipeline.input import read_isbn_inputs
from book_store_assistant.pipeline.process_results import ProcessResult
from book_store_assistant.publisher_identity.models import PublisherIdentityResult
from book_store_assistant.publisher_identity.service import (
    attach_publisher_identities,
    resolve_publisher_identities,
)
from book_store_assistant.resolution.providers import (
    build_default_bibliographic_extractor,
    build_default_record_quality_validator,
)
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.resolution.service import resolve_all
from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.diagnostics import changed_record_fields, with_diagnostic
from book_store_assistant.sources.models import SourceBookRecord
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
from book_store_assistant.sources.staged import fetch_with_stages
from book_store_assistant.sources.web_search import augment_fetch_results_with_web_search

StatusUpdateCallback = Callable[[str], None]


def _needs_bibliographic_completion(result: FetchResult) -> bool:
    if result.record is None:
        return True
    return not (
        bool((result.record.title or "").strip())
        and bool((result.record.author or "").strip())
        and bool((result.record.editorial or "").strip())
    )


def _record_uses_web_search(record: SourceBookRecord | None) -> bool:
    if record is None:
        return False

    return any(
        source_name.casefold().startswith("web_search")
        for source_name in record.field_sources.values()
    )


def _bibliographic_field_count(record: SourceBookRecord | None) -> int:
    if record is None:
        return 0

    return sum(
        bool((getattr(record, field_name) or "").strip())
        for field_name in ("title", "author", "editorial")
    )


def _web_search_unlocked_isbns(
    previous_results: list[FetchResult],
    current_results: list[FetchResult],
) -> set[str]:
    previous_by_isbn = {result.isbn: result for result in previous_results}
    unlocked_isbns: set[str] = set()

    for result in current_results:
        previous = previous_by_isbn.get(result.isbn)
        previous_record = previous.record if previous is not None else None
        current_record = result.record
        if not _record_uses_web_search(current_record):
            continue
        if _record_uses_web_search(previous_record):
            continue
        if _bibliographic_field_count(current_record) > _bibliographic_field_count(previous_record):
            unlocked_isbns.add(result.isbn)

    return unlocked_isbns


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


def _retailer_unlocked_publisher_lookup(
    result: FetchResult,
    previous_editorial: str | None,
) -> bool:
    return (
        _needs_bibliographic_completion(result)
        and result.record is not None
        and previous_editorial is None
        and result.record.field_sources.get("editorial", "").startswith("retailer_page:")
    )


def _attach_publisher_identity_results(
    resolution_results: list[ResolutionResult],
    publisher_identity_results: list[PublisherIdentityResult],
) -> list[ResolutionResult]:
    attached_results: list[ResolutionResult] = []

    for resolution_result, publisher_identity_result in zip(
        resolution_results,
        publisher_identity_results,
        strict=True,
    ):
        attached_results.append(
            resolution_result.model_copy(
                update={"publisher_identity": publisher_identity_result}
            )
        )

    return attached_results


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
    web_search_unlocked_isbns: set[str] = set()
    if app_config.web_search_fallback_enabled:
        fetch_results_before_web_search = [result.model_copy(deep=True) for result in fetch_results]
        fetch_results = augment_fetch_results_with_web_search(
            fetch_results,
            timeout_seconds=app_config.web_search_timeout_seconds,
            extractor=extractor,
            on_status_update=on_status_update,
            max_retries=app_config.publisher_page_max_retries,
            backoff_seconds=app_config.web_search_backoff_seconds,
            max_pages_per_record=app_config.web_search_max_pages_per_record,
            max_search_attempts_per_record=(
                app_config.web_search_max_search_attempts_per_record
            ),
            max_fetch_attempts_per_record=(
                app_config.web_search_max_fetch_attempts_per_record
            ),
            allow_contextual_matches=True,
            status_label="preliminary",
        )
        fetch_results = _annotate_stage_updates(
            fetch_results_before_web_search,
            fetch_results,
            "web_search_preliminary",
        )
        web_search_unlocked_isbns = _web_search_unlocked_isbns(
            fetch_results_before_web_search,
            fetch_results,
        )
    retailer_editorial_before = {
        result.isbn: result.record.editorial if result.record is not None else None
        for result in fetch_results
    }
    if app_config.retailer_page_lookup_enabled:
        retailer_before = [result.model_copy(deep=True) for result in fetch_results]
        fetch_results = augment_fetch_results_with_retailer_editorials(
            fetch_results,
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
            force_lookup_isbns=web_search_unlocked_isbns,
        )
        fetch_results = _annotate_stage_updates(
            retailer_before,
            fetch_results,
            "retailer_lookup",
        )
    publisher_candidate_isbns = {
        result.isbn
        for result in fetch_results
        if result.record is not None
        and bool((result.record.editorial or "").strip())
        and _needs_bibliographic_completion(result)
    }
    retailer_unlocked_isbns = {
        result.isbn
        for result in fetch_results
        if _retailer_unlocked_publisher_lookup(
            result,
            retailer_editorial_before.get(result.isbn),
        )
    }
    initial_publisher_candidate_isbns = (
        publisher_candidate_isbns - retailer_unlocked_isbns
    ) | web_search_unlocked_isbns
    if app_config.publisher_page_lookup_enabled and initial_publisher_candidate_isbns:
        publisher_pages_before = [result.model_copy(deep=True) for result in fetch_results]
        fetch_results = augment_fetch_results_with_publisher_pages(
            fetch_results,
            timeout_seconds=app_config.publisher_page_timeout_seconds,
            on_status_update=on_status_update,
            max_retries=app_config.publisher_page_max_retries,
            backoff_seconds=app_config.publisher_page_backoff_seconds,
            eligible_isbns=initial_publisher_candidate_isbns,
            max_profiles_per_record=app_config.publisher_page_max_profiles_per_record,
            max_search_attempts_per_record=(
                app_config.publisher_page_max_search_attempts_per_record
            ),
            max_fetch_attempts_per_record=(
                app_config.publisher_page_max_fetch_attempts_per_record
            ),
            force_lookup_isbns=web_search_unlocked_isbns,
        )
        fetch_results = _annotate_stage_updates(
            publisher_pages_before,
            fetch_results,
            "publisher_pages",
        )
    if app_config.publisher_page_lookup_enabled and retailer_unlocked_isbns:
        publisher_pages_before = [result.model_copy(deep=True) for result in fetch_results]
        fetch_results = augment_fetch_results_with_publisher_pages(
            fetch_results,
            timeout_seconds=app_config.publisher_page_timeout_seconds,
            on_status_update=on_status_update,
            max_retries=app_config.publisher_page_max_retries,
            backoff_seconds=app_config.publisher_page_backoff_seconds,
            eligible_isbns=retailer_unlocked_isbns,
            max_profiles_per_record=app_config.publisher_page_max_profiles_per_record,
            max_search_attempts_per_record=(
                app_config.publisher_page_max_search_attempts_per_record
            ),
            max_fetch_attempts_per_record=(
                app_config.publisher_page_max_fetch_attempts_per_record
            ),
            force_lookup_isbns=web_search_unlocked_isbns,
        )
        fetch_results = _annotate_stage_updates(
            publisher_pages_before,
            fetch_results,
            "publisher_pages",
        )
    if app_config.publisher_page_lookup_enabled:
        publisher_discovery_before = [result.model_copy(deep=True) for result in fetch_results]
        fetch_results = augment_fetch_results_with_publisher_discovery(
            fetch_results,
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
            force_lookup_isbns=web_search_unlocked_isbns,
        )
        fetch_results = _annotate_stage_updates(
            publisher_discovery_before,
            fetch_results,
            "publisher_discovery",
        )
    if app_config.web_search_fallback_enabled:
        fallback_before = [result.model_copy(deep=True) for result in fetch_results]
        fetch_results = augment_fetch_results_with_web_search(
            fetch_results,
            timeout_seconds=app_config.web_search_timeout_seconds,
            extractor=extractor,
            on_status_update=on_status_update,
            max_retries=app_config.publisher_page_max_retries,
            backoff_seconds=app_config.web_search_backoff_seconds,
            max_pages_per_record=app_config.web_search_max_pages_per_record,
            max_search_attempts_per_record=(
                app_config.web_search_max_search_attempts_per_record
            ),
            max_fetch_attempts_per_record=(
                app_config.web_search_max_fetch_attempts_per_record
            ),
            status_label="fallback",
        )
        fetch_results = _annotate_stage_updates(
            fallback_before,
            fetch_results,
            "web_search_fallback",
        )
    publisher_identity_results = resolve_publisher_identities(fetch_results)
    fetch_results = attach_publisher_identities(fetch_results, publisher_identity_results)
    resolution_results = resolve_all(fetch_results, validator=validator)
    resolution_results = _attach_publisher_identity_results(
        resolution_results,
        publisher_identity_results,
    )

    return ProcessResult(
        input_result=input_result,
        fetch_results=fetch_results,
        publisher_identity_results=publisher_identity_results,
        resolution_results=resolution_results,
    )
