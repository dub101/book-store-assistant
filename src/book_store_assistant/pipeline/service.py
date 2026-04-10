from collections.abc import Callable
from pathlib import Path

from book_store_assistant.config import AppConfig
from book_store_assistant.pipeline.input import read_isbn_inputs
from book_store_assistant.pipeline.process_results import ProcessResult
from book_store_assistant.resolution.providers import (
    build_default_llm_enricher,
    build_default_record_quality_validator,
)
from book_store_assistant.resolution.service import resolve_all
from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.llm_enrichment import augment_fetch_results_with_llm_enrichment
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.service import (
    FetchCompleteCallback,
    FetchStartCallback,
    fetch_all,
)
from book_store_assistant.sources.staged import fetch_with_stages

StatusUpdateCallback = Callable[[str], None]


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
    enricher = build_default_llm_enricher(app_config)

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
        fetch_results = fetch_all(
            source,
            input_result.valid_inputs,
            on_fetch_start=on_fetch_start,
            on_fetch_complete=on_fetch_complete,
        )

    if enricher is not None:
        fetch_results = augment_fetch_results_with_llm_enrichment(
            fetch_results,
            enricher=enricher,
            on_status_update=on_status_update,
        )

    resolution_results = resolve_all(fetch_results, validator=validator)

    return ProcessResult(
        input_result=input_result,
        fetch_results=fetch_results,
        resolution_results=resolution_results,
    )
