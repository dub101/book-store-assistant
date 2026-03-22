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
    retailer_editorial_before = {
        result.isbn: result.record.editorial if result.record is not None else None
        for result in fetch_results
    }
    if app_config.retailer_page_lookup_enabled:
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
    initial_publisher_candidate_isbns = publisher_candidate_isbns - retailer_unlocked_isbns
    if app_config.publisher_page_lookup_enabled and initial_publisher_candidate_isbns:
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
        )
    if app_config.publisher_page_lookup_enabled and retailer_unlocked_isbns:
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
        )
    if app_config.publisher_page_lookup_enabled:
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
        )
    if app_config.web_search_fallback_enabled:
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
