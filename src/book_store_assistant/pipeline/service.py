from pathlib import Path

from book_store_assistant.pipeline.input import read_isbn_inputs
from book_store_assistant.pipeline.results import InputReadResult


def process_isbn_file(input_path: Path) -> InputReadResult:
    """Read a CSV file and return structured input validation results."""
    return read_isbn_inputs(input_path)
