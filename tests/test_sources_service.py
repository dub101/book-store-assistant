from book_store_assistant.pipeline.contracts import ISBNInput
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.service import fetch_all


class DummySource:
    def fetch(self, isbn: str) -> FetchResult:
        return FetchResult(isbn=isbn, record=None, errors=[])


def test_fetch_all_calls_source_for_each_isbn() -> None:
    source = DummySource()
    inputs = [ISBNInput(isbn="9780306406157"), ISBNInput(isbn="0306406152")]

    results = fetch_all(source, inputs)

    assert [result.isbn for result in results] == ["9780306406157", "0306406152"]
