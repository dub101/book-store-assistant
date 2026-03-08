from book_store_assistant.resolution.books import resolve_book_record
from book_store_assistant.sources.models import SourceBookRecord


def test_resolve_book_record_returns_errors_when_required_fields_are_missing() -> None:
    source_record = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        title="Example Title",
        author="Example Author",
        editorial="Example Editorial",
    )

    result = resolve_book_record(source_record)

    assert result.record is None
    assert "Synopsis is missing." in result.errors
    assert "Subject is missing." in result.errors


def test_resolve_book_record_builds_book_record_when_required_fields_exist() -> None:
    source_record = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        title="Example Title",
        author="Example Author",
        editorial="Example Editorial",
        synopsis="Resumen del libro.",
        subject="Narrativa",
    )

    result = resolve_book_record(source_record)

    assert result.record is not None
    assert result.record.title == "Example Title"
    assert result.record.subject == "Narrativa"
    assert result.errors == []
