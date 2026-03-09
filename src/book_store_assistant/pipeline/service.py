from pathlib import Path

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
    on_fetch_start: FetchStartCallback | None = None,
    on_fetch_complete: FetchCompleteCallback | None = None,
) -> ProcessResult:
    """Read ISBNs, fetch metadata, and resolve source records."""
    input_result = read_isbn_inputs(input_path)
    active_source = source or build_default_source()
    fetch_results = fetch_all(
        active_source,
        input_result.valid_inputs,
        on_fetch_start=on_fetch_start,
        on_fetch_complete=on_fetch_complete,
    )
    resolution_results = resolve_all(fetch_results)

    return ProcessResult(
        input_result=input_result,
        fetch_results=fetch_results,
        resolution_results=resolution_results,
    )
