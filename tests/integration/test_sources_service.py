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


def test_fetch_all_reports_start_and_completion_callbacks() -> None:
    source = DummySource()
    inputs = [ISBNInput(isbn="9780306406157"), ISBNInput(isbn="0306406152")]
    starts: list[tuple[int, int, str]] = []
    completions: list[tuple[int, int, str]] = []

    results = fetch_all(
        source,
        inputs,
        on_fetch_start=lambda index, total, isbn: starts.append((index, total, isbn)),
        on_fetch_complete=lambda index, total, result: completions.append(
            (index, total, result.isbn)
        ),
    )

    assert [result.isbn for result in results] == ["9780306406157", "0306406152"]
    assert starts == [
        (1, 2, "9780306406157"),
        (2, 2, "0306406152"),
    ]
    assert completions == [
        (1, 2, "9780306406157"),
        (2, 2, "0306406152"),
    ]
