from pathlib import Path

from book_store_assistant.config import AppConfig, ExecutionMode
from book_store_assistant.enrichment.base import SourceRecordEnricher
from book_store_assistant.enrichment.service import enrich_fetch_results
from book_store_assistant.pipeline.input import read_isbn_inputs
from book_store_assistant.pipeline.process_results import ProcessResult
from book_store_assistant.resolution.service import resolve_all
from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.defaults import build_default_sources
from book_store_assistant.sources.fallback import FallbackMetadataSource
from book_store_assistant.sources.service import (
    FetchCompleteCallback,
    FetchStartCallback,
    fetch_all,
)


def build_default_source() -> MetadataSource:
    return FallbackMetadataSource(build_default_sources())


def process_isbn_file(
    input_path: Path,
    source: MetadataSource | None = None,
    config: AppConfig | None = None,
    mode: ExecutionMode | None = None,
    enricher: SourceRecordEnricher | None = None,
    on_fetch_start: FetchStartCallback | None = None,
    on_fetch_complete: FetchCompleteCallback | None = None,
) -> ProcessResult:
    """Read ISBNs, fetch metadata, and resolve source records."""
    app_config = config or AppConfig()
    active_mode = mode or app_config.execution_mode
    input_result = read_isbn_inputs(input_path)
    active_source = source or build_default_source()
    fetch_results = fetch_all(
        active_source,
        input_result.valid_inputs,
        on_fetch_start=on_fetch_start,
        on_fetch_complete=on_fetch_complete,
    )
    enriched_fetch_results, enrichment_results = enrich_fetch_results(
        fetch_results,
        mode=active_mode,
        enricher=enricher,
    )
    resolution_results = resolve_all(enriched_fetch_results)

    return ProcessResult(
        input_result=input_result,
        fetch_results=enriched_fetch_results,
        enrichment_results=enrichment_results,
        resolution_results=resolution_results,
    )
