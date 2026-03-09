from book_store_assistant.resolution.service import resolve_all
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


def test_resolve_all_handles_fetch_errors_and_resolved_records() -> None:
    fetch_results = [
        FetchResult(isbn="9780306406157", record=None, errors=["No Google Books match found."]),
        FetchResult(
            isbn="0306406152",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="0306406152",
                title="Example Title",
                author="Example Author",
                editorial="Example Editorial",
                synopsis="Resumen del libro.",
                subject="Narrativa",
            ),
            errors=[],
        ),
    ]

    results = resolve_all(fetch_results)

    assert results[0].record is None
    assert results[0].source_record is not None
    assert results[0].source_record.source_name == "fetch_error"
    assert results[0].source_record.isbn == "9780306406157"
    assert results[0].errors == ["No Google Books match found."]
    assert results[1].record is not None
    assert results[1].record.isbn == "0306406152"
