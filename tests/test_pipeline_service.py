from pathlib import Path

from book_store_assistant.pipeline.service import process_isbn_file
from book_store_assistant.sources.results import FetchResult


class DummySource:
    def fetch(self, isbn: str) -> FetchResult:
        return FetchResult(isbn=isbn, record=None, errors=["No match"])


def test_process_isbn_file_uses_injected_source(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\ninvalid\n", encoding="utf-8")

    result = process_isbn_file(input_file, source=DummySource())

    assert len(result.input_result.valid_inputs) == 1
    assert result.input_result.invalid_values == ["invalid"]
    assert len(result.fetch_results) == 1
    assert result.fetch_results[0].errors == ["No match"]
