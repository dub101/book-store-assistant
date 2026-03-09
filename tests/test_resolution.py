from pathlib import Path

from book_store_assistant.resolution.books import resolve_book_record
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
    )

    result = resolve_book_record(source_record, subjects_path=subject_file)

    assert result.record is None
    assert "Synopsis is missing." in result.errors
    assert "Subject is missing." in result.errors


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
    )

    result = resolve_book_record(source_record, subjects_path=subject_file)

    assert result.record is None
    assert "Synopsis is missing." not in result.errors
    assert result.errors == [NON_SPANISH_SYNOPSIS_REVIEW_ERROR]
