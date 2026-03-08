from pathlib import Path

from book_store_assistant.pipeline.input import read_isbn_inputs
from book_store_assistant.pipeline.process_results import ProcessResult
from book_store_assistant.resolution.service import resolve_all
from book_store_assistant.sources.google_books import GoogleBooksSource
from book_store_assistant.sources.service import fetch_all


def process_isbn_file(input_path: Path) -> ProcessResult:
    """Read ISBNs, fetch metadata, and resolve source records."""
    input_result = read_isbn_inputs(input_path)
    source = GoogleBooksSource()
    fetch_results = fetch_all(source, input_result.valid_inputs)
    resolution_results = resolve_all(fetch_results)

    return ProcessResult(
        input_result=input_result,
        fetch_results=fetch_results,
        resolution_results=resolution_results,
    )
