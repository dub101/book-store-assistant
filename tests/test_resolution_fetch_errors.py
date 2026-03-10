from book_store_assistant.resolution.service import FETCH_ERROR_CODE, resolve_all
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
            issue_codes=["GOOGLE_BOOKS:GOOGLE_BOOKS_TIMEOUT"],
        )
    ]

    results = resolve_all(fetch_results)

    assert len(results) == 1
    assert results[0].record is None
    assert results[0].source_record is not None
    assert results[0].source_record.source_name == "google_books + open_library"
    assert results[0].reason_codes == [
        FETCH_ERROR_CODE,
        "MISSING_AUTHOR",
        "MISSING_EDITORIAL",
        "MISSING_SYNOPSIS",
        "MISSING_SUBJECT",
    ]
    assert results[0].review_details == [
        "Source issue: GOOGLE_BOOKS:GOOGLE_BOOKS_TIMEOUT.",
        "google_books: Timeout",
        "No source supplied author.",
        "No source supplied editorial.",
        "No source supplied synopsis.",
        "No source supplied subject or usable categories.",
    ]
