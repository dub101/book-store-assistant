from pathlib import Path

from book_store_assistant.resolution.books import (
    SUBJECT_MISSING_ERROR,
    SYNOPSIS_MISSING_ERROR,
    resolve_book_record,
)
from book_store_assistant.resolution.synopsis_resolution import NON_SPANISH_SYNOPSIS_REVIEW_ERROR
from book_store_assistant.sources.models import SourceBookRecord


def test_resolve_book_record_returns_errors_when_required_fields_are_missing(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.txt"
    subject_file.write_text("Narrativa\nHistoria\n", encoding="utf-8")

    source_record = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        title="Example Title",
        author="Example Author",
        editorial="Example Editorial",
        field_sources={
            "title": "google_books",
            "author": "google_books",
            "editorial": "google_books",
        },
    )

    result = resolve_book_record(source_record, subjects_path=subject_file)

    assert result.record is None
    assert SYNOPSIS_MISSING_ERROR in result.errors
    assert SUBJECT_MISSING_ERROR in result.errors
    assert "Review detail: no source supplied synopsis." in result.errors
    assert "Review detail: no source supplied subject or usable categories." in result.errors


def test_resolve_book_record_builds_book_record_when_required_fields_exist(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.txt"
    subject_file.write_text("Narrativa\nHistoria\n", encoding="utf-8")

    source_record = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        title="Example Title",
        author="Example Author",
        editorial="Example Editorial",
        synopsis="Resumen del libro.",
        subject="Narrativa",
        language="es",
    )

    result = resolve_book_record(source_record, subjects_path=subject_file)

    assert result.record is not None
    assert result.record.title == "Example Title"
    assert result.record.subject == "Narrativa"
    assert result.record.synopsis == "Resumen del libro."
    assert result.errors == []


def test_resolve_book_record_uses_matching_category_as_subject(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.txt"
    subject_file.write_text("Narrativa\nHistoria\n", encoding="utf-8")

    source_record = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        title="Example Title",
        author="Example Author",
        editorial="Example Editorial",
        synopsis="Resumen del libro.",
        language="es",
        categories=["Poetry", "Historia"],
        field_sources={"categories": "google_books"},
    )

    result = resolve_book_record(source_record, subjects_path=subject_file)

    assert result.record is not None
    assert result.record.subject == "Historia"


def test_resolve_book_record_marks_non_spanish_synopsis_for_review(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.txt"
    subject_file.write_text("Narrativa\nHistoria\n", encoding="utf-8")

    source_record = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        title="Example Title",
        author="Example Author",
        editorial="Example Editorial",
        synopsis="Book description.",
        subject="Narrativa",
        language="en",
        field_sources={
            "title": "google_books",
            "author": "google_books",
            "editorial": "google_books",
            "synopsis": "google_books",
            "subject": "google_books",
            "language": "google_books",
        },
    )

    result = resolve_book_record(source_record, subjects_path=subject_file)

    assert result.record is None
    assert SYNOPSIS_MISSING_ERROR not in result.errors
    assert NON_SPANISH_SYNOPSIS_REVIEW_ERROR in result.errors
    assert "Review detail: synopsis came from google_books with language 'en'." in result.errors
