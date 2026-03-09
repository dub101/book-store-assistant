from book_store_assistant.resolution.service import resolve_all
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


def test_resolve_all_preserves_fetch_errors_for_unresolved_records() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books + open_library",
                isbn="9780306406157",
                title="Example Title",
                field_sources={"title": "google_books"},
            ),
            errors=["google_books: Timeout"],
        )
    ]

    results = resolve_all(fetch_results)

    assert len(results) == 1
    assert results[0].record is None
    assert results[0].source_record is not None
    assert results[0].source_record.source_name == "google_books + open_library"
    assert results[0].errors == [
        "google_books: Timeout",
        "Author is missing.",
        "Editorial is missing.",
        "Synopsis is missing.",
        "Subject is missing.",
        "Review detail: no source supplied author.",
        "Review detail: no source supplied editorial.",
        "Review detail: no source supplied synopsis.",
        "Review detail: no source supplied subject or usable categories.",
    ]
