from pathlib import Path

from book_store_assistant.resolution.books import (
    NON_SPANISH_SYNOPSIS_CODE,
    SUBJECT_MISSING_CODE,
    resolve_book_record,
)
from book_store_assistant.resolution.synopsis_resolution import (
    NON_SPANISH_SYNOPSIS_REVIEW_ERROR,
)
from book_store_assistant.sources.models import SourceBookRecord


class StubSubjectMapper:
    def __init__(self, subject: str | None) -> None:
        self.subject = subject

    def map_subject(self, record, allowed_subject_entries) -> str | None:
        return self.subject


def test_resolve_book_record_returns_book_when_required_fields_are_present(tmp_path: Path) -> None:
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
    assert result.reason_codes == []
    assert result.review_details == []


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


def test_resolve_book_record_ignores_non_book_subject_types(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.tsv"
    subject_file.write_text(
        "Subject\tDescription\tSubject_Type\n"
        "22\tPELUCHES Y TITERES\tP0\n"
        "13\tFICCION\tL0\n",
        encoding="utf-8",
    )

    source_record = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        title="Example Title",
        author="Example Author",
        editorial="Example Editorial",
        synopsis="Resumen del libro.",
        language="es",
        categories=["Peluches y titeres"],
        field_sources={"categories": "google_books"},
    )

    result = resolve_book_record(source_record, subjects_path=subject_file)

    assert result.record is None
    assert result.reason_codes == [SUBJECT_MISSING_CODE]
    assert "Subject is missing." in result.errors


def test_resolve_book_record_rejects_unmapped_direct_subject(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.tsv"
    subject_file.write_text(
        "Subject\tDescription\tSubject_Type\n"
        "13\tFICCION\tL0\n",
        encoding="utf-8",
    )

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

    assert result.record is None
    assert result.reason_codes == [SUBJECT_MISSING_CODE]
    assert result.review_details == [
        "Subject 'Narrativa' did not resolve to an allowed bookstore subject."
    ]


def test_resolve_book_record_uses_tabular_subject_alias_for_category(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.tsv"
    subject_file.write_text(
        "Subject\tDescription\tSubject_Type\tAliases\n"
        "1301\tLITERATURA Y NOVELA\tL0\tRomance literature | Literature\n",
        encoding="utf-8",
    )

    source_record = SourceBookRecord(
        source_name="google_books + open_library",
        isbn="9788467035704",
        title="Don Quijote de la Mancha",
        author="Miguel de Cervantes Saavedra",
        editorial="Austral",
        synopsis="Resumen del libro.",
        language="es",
        categories=["Literary Criticism", "Romance literature"],
        field_sources={"categories": "google_books + open_library"},
    )

    result = resolve_book_record(source_record, subjects_path=subject_file)

    assert result.record is not None
    assert result.record.subject == "LITERATURA Y NOVELA"


def test_resolve_book_record_uses_tabular_subject_alias_for_direct_subject(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.tsv"
    subject_file.write_text(
        "Subject\tDescription\tSubject_Type\tAliases\n"
        "1301\tLITERATURA Y NOVELA\tL0\tRomance literature | Literature\n",
        encoding="utf-8",
    )

    source_record = SourceBookRecord(
        source_name="google_books",
        isbn="9788467035704",
        title="Don Quijote de la Mancha",
        author="Miguel de Cervantes Saavedra",
        editorial="Austral",
        synopsis="Resumen del libro.",
        subject="Romance literature",
        language="es",
        field_sources={"subject": "google_books"},
    )

    result = resolve_book_record(source_record, subjects_path=subject_file)

    assert result.record is not None
    assert result.record.subject == "LITERATURA Y NOVELA"


def test_resolve_book_record_uses_subject_mapper_when_rule_mapping_fails(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.tsv"
    subject_file.write_text(
        "Subject\tDescription\tSubject_Type\n"
        "13\tFICCION\tL0\n",
        encoding="utf-8",
    )

    source_record = SourceBookRecord(
        source_name="open_library",
        isbn="9780306406157",
        title="Example Title",
        author="Example Author",
        editorial="Example Editorial",
        synopsis="Resumen del libro.",
        language="es",
        categories=["Narrative fiction"],
    )

    result = resolve_book_record(
        source_record,
        subjects_path=subject_file,
        subject_mapper=StubSubjectMapper("FICCION"),
    )

    assert result.record is not None
    assert result.record.subject == "FICCION"


def test_resolve_book_record_uses_subject_mapper_when_direct_subject_is_unmapped(
    tmp_path: Path,
) -> None:
    subject_file = tmp_path / "subjects.tsv"
    subject_file.write_text(
        "Subject\tDescription\tSubject_Type\n"
        "13\tFICCION\tL0\n",
        encoding="utf-8",
    )

    source_record = SourceBookRecord(
        source_name="open_library",
        isbn="9780306406157",
        title="Example Title",
        author="Example Author",
        editorial="Example Editorial",
        synopsis="Resumen del libro.",
        subject="Narrativa contemporanea",
        language="es",
    )

    result = resolve_book_record(
        source_record,
        subjects_path=subject_file,
        subject_mapper=StubSubjectMapper("FICCION"),
    )

    assert result.record is not None
    assert result.record.subject == "FICCION"


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
    assert result.reason_codes == [NON_SPANISH_SYNOPSIS_CODE]
    assert result.review_details == ["Synopsis came from google_books with language 'en'."]
    assert NON_SPANISH_SYNOPSIS_REVIEW_ERROR in result.errors
