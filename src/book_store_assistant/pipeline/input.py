import csv
from pathlib import Path

from book_store_assistant.isbn import is_valid_isbn, normalize_isbn
from book_store_assistant.pipeline.contracts import ISBNInput
from book_store_assistant.pipeline.results import InputReadResult


def read_isbn_inputs(input_path: Path) -> InputReadResult:
    """Read ISBN values from a CSV file and split valid rows from invalid ones."""
    valid_inputs: list[ISBNInput] = []
    invalid_values: list[str] = []

    with input_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            if not row:
                continue

            normalized_isbn = normalize_isbn(row[0])
            if is_valid_isbn(normalized_isbn):
                valid_inputs.append(ISBNInput(isbn=normalized_isbn))
            else:
                invalid_values.append(row[0])

    return InputReadResult(valid_inputs=valid_inputs, invalid_values=invalid_values)
