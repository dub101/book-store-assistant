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
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.resolution.service import resolve_all
from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.defaults import build_default_sources
from book_store_assistant.sources.fallback import FallbackMetadataSource
from book_store_assistant.sources.publisher_pages import (
    augment_fetch_results_with_publisher_pages,
)
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.service import (
    FetchCompleteCallback,
    FetchStartCallback,
    fetch_all,
)


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


def build_default_source() -> MetadataSource:
    return FallbackMetadataSource(build_default_sources())


def process_isbn_file(
    input_path: Path,
    source: MetadataSource | None = None,
    config: AppConfig | None = None,
    mode: ExecutionMode | None = None,
    enricher: SourceRecordEnricher | None = None,
    generator: SynopsisGenerator | None = None,
    on_fetch_start: FetchStartCallback | None = None,
    on_fetch_complete: FetchCompleteCallback | None = None,
    on_enrichment_start: EnrichmentStartCallback | None = None,
    on_enrichment_complete: EnrichmentCompleteCallback | None = None,
) -> ProcessResult:
    """Read ISBNs, fetch metadata, and resolve source records."""
    app_config = config or AppConfig()
    active_mode = mode or app_config.execution_mode
    input_result = read_isbn_inputs(input_path)
    active_source = source or build_default_source()
    active_generator = generator or build_default_synopsis_generator(app_config)
    page_fetcher = HttpPageContentFetcher(app_config.request_timeout_seconds)
    fetch_results: list[FetchResult] = fetch_all(
        active_source,
        input_result.valid_inputs,
        on_fetch_start=on_fetch_start,
        on_fetch_complete=on_fetch_complete,
    )
    if app_config.publisher_page_lookup_enabled:
        fetch_results = augment_fetch_results_with_publisher_pages(
            fetch_results,
            timeout_seconds=app_config.request_timeout_seconds,
        )
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
        enriched_resolution_results = resolve_all(enriched_fetch_results)
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

    return ProcessResult(
        input_result=input_result,
        fetch_results=enriched_fetch_results,
        enrichment_results=enrichment_results,
        resolution_results=resolution_results,
    )
