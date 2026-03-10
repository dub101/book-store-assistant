from book_store_assistant.export.rows import build_books_row, build_review_row
from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.models import SourceBookRecord


def test_build_books_row_returns_expected_values() -> None:
    record = BookRecord(
        isbn="9780306406157",
        title="Example Title",
        subtitle="Example Subtitle",
        author="Example Author",
        editorial="Example Editorial",
        synopsis="Resumen del libro.",
        subject="FICCION",
        cover_url="https://example.com/cover.jpg",
    )

    row = build_books_row(record)

    assert row == [
        "9780306406157",
        "Example Title",
        "Example Subtitle",
        "Example Author",
        "Example Editorial",
        "Resumen del libro.",
        "FICCION",
        "13",
        "https://example.com/cover.jpg",
    ]


def test_build_review_row_returns_expected_values() -> None:
    result = ResolutionResult(
        record=None,
        source_record=SourceBookRecord(
            source_name="google_books + open_library",
            isbn="9780306406157",
            title="Example Title",
            subtitle="Example Subtitle",
            author="Example Author",
            editorial="Example Editorial",
            synopsis="Book description.",
            subject="FICCION",
            language="en",
            categories=["Fiction", "Literature"],
            cover_url="https://example.com/cover.jpg",
            field_sources={
                "title": "google_books",
                "editorial": "open_library",
            },
        ),
        errors=[],
        reason_codes=["MISSING_SYNOPSIS"],
        review_details=["Synopsis came from google_books with language 'en'."],
    )

    row = build_review_row(result)

    assert row == [
        "9780306406157",
        "Example Title",
        "Example Subtitle",
        "Example Author",
        "Example Editorial",
        "google_books + open_library",
        "en",
        "FICCION",
        "13",
        "L0",
        "Fiction, Literature",
        "https://example.com/cover.jpg",
        "Book description.",
        "editorial=open_library; title=google_books",
        None,
        None,
        None,
        "MISSING_SYNOPSIS",
        "Synopsis came from google_books with language 'en'.",
    ]
