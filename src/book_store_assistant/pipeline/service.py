from collections.abc import Callable
from pathlib import Path

from book_store_assistant.config import AppConfig, ExecutionMode
from book_store_assistant.enrichment.base import SourceRecordEnricher, SynopsisGenerator
from book_store_assistant.enrichment.models import EnrichmentResult
from book_store_assistant.enrichment.page_fetch import HttpPageContentFetcher
from book_store_assistant.enrichment.providers import build_default_synopsis_generator
from book_store_assistant.enrichment.service import (
    EnrichmentCompleteCallback,
    EnrichmentStartCallback,
    enrich_fetch_results,
)
from book_store_assistant.pipeline.input import read_isbn_inputs
from book_store_assistant.pipeline.process_results import ProcessResult
from book_store_assistant.publisher_identity.models import PublisherIdentityResult
from book_store_assistant.publisher_identity.service import (
    attach_publisher_identities,
    resolve_publisher_identities,
)
from book_store_assistant.resolution.base import SubjectMapper
from book_store_assistant.resolution.providers import build_default_subject_mapper
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.resolution.service import resolve_all
from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.cache import FetchResultCache
from book_store_assistant.sources.defaults import build_default_sources, wrap_with_default_cache
from book_store_assistant.sources.fallback import FallbackMetadataSource
from book_store_assistant.sources.publisher_pages import (
    PUBLISHER_PAGE_CACHE_KEY,
    augment_fetch_results_with_publisher_pages,
)
from book_store_assistant.sources.retailer_pages import (
    augment_fetch_results_with_retailer_editorials,
)
from book_store_assistant.sources.service import (
    FetchCompleteCallback,
    FetchStartCallback,
    fetch_all,
)
from book_store_assistant.sources.staged import fetch_with_intermediate_stages

StatusUpdateCallback = Callable[[str], None]


def _attach_enrichment_results(
    resolution_results: list[ResolutionResult],
    enrichment_results: list[EnrichmentResult],
) -> list[ResolutionResult]:
    attached_results: list[ResolutionResult] = []

    for resolution_result, enrichment_result in zip(
        resolution_results,
        enrichment_results,
        strict=True,
    ):
        attached_results.append(
            resolution_result.model_copy(update={"enrichment_result": enrichment_result})
        )

    return attached_results


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


def _select_best_resolution_results(
    baseline_results: list[ResolutionResult],
    enriched_results: list[ResolutionResult],
) -> list[ResolutionResult]:
    selected_results: list[ResolutionResult] = []

    for baseline_result, enriched_result in zip(
        baseline_results,
        enriched_results,
        strict=True,
    ):
        if enriched_result.record is not None:
            selected_results.append(enriched_result)
            continue

        if baseline_result.record is not None:
            selected_results.append(baseline_result)
            continue

        selected_results.append(enriched_result)

    return selected_results


def build_default_source(config: AppConfig | None = None) -> MetadataSource:
    active_config = config or AppConfig()
    base_source = FallbackMetadataSource(build_default_sources(active_config))
    return wrap_with_default_cache(base_source, active_config)


def process_isbn_file(
    input_path: Path,
    source: MetadataSource | None = None,
    config: AppConfig | None = None,
    mode: ExecutionMode | None = None,
    enricher: SourceRecordEnricher | None = None,
    generator: SynopsisGenerator | None = None,
    subject_mapper: SubjectMapper | None = None,
    on_fetch_start: FetchStartCallback | None = None,
    on_fetch_complete: FetchCompleteCallback | None = None,
    on_enrichment_start: EnrichmentStartCallback | None = None,
    on_enrichment_complete: EnrichmentCompleteCallback | None = None,
    on_status_update: StatusUpdateCallback | None = None,
) -> ProcessResult:
    """Read ISBNs, fetch metadata, and resolve source records."""
    app_config = config or AppConfig()
    active_mode = mode or app_config.execution_mode
    input_result = read_isbn_inputs(input_path)
    active_generator = generator or build_default_synopsis_generator(app_config)
    active_subject_mapper = (
        subject_mapper
        or build_default_subject_mapper(app_config)
        if active_mode is ExecutionMode.AI_ENRICHED
        else None
    )
    page_fetcher = HttpPageContentFetcher(app_config.request_timeout_seconds)
    if source is None:
        fetch_results = fetch_with_intermediate_stages(
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
    publisher_page_cache = (
        FetchResultCache(app_config.publisher_page_cache_dir, PUBLISHER_PAGE_CACHE_KEY)
        if app_config.publisher_page_cache_enabled
        else None
    )
    fetch_results = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=app_config.publisher_page_timeout_seconds,
        on_status_update=on_status_update,
        cache=publisher_page_cache,
        cache_ttl_seconds=app_config.publisher_page_negative_cache_ttl_seconds,
        max_retries=app_config.publisher_page_max_retries,
        backoff_seconds=app_config.publisher_page_backoff_seconds,
    )
    retailer_editorial_before = {
        result.isbn: result.record.editorial if result.record is not None else None
        for result in fetch_results
    }
    fetch_results = augment_fetch_results_with_retailer_editorials(
        fetch_results,
        timeout_seconds=app_config.publisher_page_timeout_seconds,
        on_status_update=on_status_update,
        max_retries=app_config.publisher_page_max_retries,
        backoff_seconds=app_config.publisher_page_backoff_seconds,
    )
    retailer_unlocked_isbns = {
        result.isbn
        for result in fetch_results
        if (
            result.record is not None
            and retailer_editorial_before.get(result.isbn) is None
            and result.record.editorial is not None
            and result.record.field_sources.get("editorial", "").startswith("retailer_page:")
        )
    }
    if retailer_unlocked_isbns:
        fetch_results = augment_fetch_results_with_publisher_pages(
            fetch_results,
            timeout_seconds=app_config.publisher_page_timeout_seconds,
            on_status_update=on_status_update,
            cache=publisher_page_cache,
            cache_ttl_seconds=app_config.publisher_page_negative_cache_ttl_seconds,
            max_retries=app_config.publisher_page_max_retries,
            backoff_seconds=app_config.publisher_page_backoff_seconds,
            eligible_isbns=retailer_unlocked_isbns,
            ignore_negative_cache=True,
        )
    publisher_identity_results = resolve_publisher_identities(fetch_results)
    fetch_results = attach_publisher_identities(fetch_results, publisher_identity_results)
    enriched_fetch_results, enrichment_results = enrich_fetch_results(
        fetch_results,
        mode=active_mode,
        enricher=enricher,
        generator=active_generator,
        page_fetcher=page_fetcher,
        on_enrichment_start=on_enrichment_start,
        on_enrichment_complete=on_enrichment_complete,
    )
    if active_mode is ExecutionMode.AI_ENRICHED:
        baseline_resolution_results = resolve_all(fetch_results)
        enriched_resolution_results = resolve_all(
            enriched_fetch_results,
            subject_mapper=active_subject_mapper,
        )
        resolution_results = _select_best_resolution_results(
            baseline_resolution_results,
            enriched_resolution_results,
        )
    else:
        resolution_results = resolve_all(enriched_fetch_results)

    resolution_results = _attach_enrichment_results(
        resolution_results,
        enrichment_results,
    )
    resolution_results = _attach_publisher_identity_results(
        resolution_results,
        publisher_identity_results,
    )

    return ProcessResult(
        input_result=input_result,
        fetch_results=enriched_fetch_results,
        publisher_identity_results=publisher_identity_results,
        enrichment_results=enrichment_results,
        resolution_results=resolution_results,
    )
