from pathlib import Path

from book_store_assistant.pipeline.contracts import ISBNInput
from book_store_assistant.pipeline.input import read_isbn_inputs


def process_isbn_file(input_path: Path) -> tuple[list[ISBNInput], list[str]]:
    """Read a CSV file and return valid ISBN inputs plus invalid raw values."""
    return read_isbn_inputs(input_path)
