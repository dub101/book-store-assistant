from pathlib import Path

from book_store_assistant.subject_loader import (
    load_subject_entries,
    load_subject_rows,
    load_subjects,
)
from book_store_assistant.subjects import SubjectEntry


def test_load_subjects_reads_non_empty_lines(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.txt"
    subject_file.write_text("Narrativa\n\nHistoria\n", encoding="utf-8")

    subjects = load_subjects(subject_file)

    assert subjects == ["Narrativa", "Historia"]


def test_load_subject_rows_supports_aliases_and_comments(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.txt"
    subject_file.write_text(
        "# canonical | aliases\n"
        "Narrativa | Ficcion | Novel\n"
        "Historia | Historical\n",
        encoding="utf-8",
    )

    rows = load_subject_rows(subject_file)

    assert rows == [
        ["Narrativa", "Ficcion", "Novel"],
        ["Historia", "Historical"],
    ]


def test_load_subject_entries_supports_tabular_catalog(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.tsv"
    subject_file.write_text(
        "Subject\tDescription\tSubject_Type\tAliases\n"
        "13\tFICCION\tL0\tFiction | Novel\n"
        "1402\tHISTORIA\tL0\tHistorical\n",
        encoding="utf-8",
    )

    entries = load_subject_entries(subject_file)

    assert entries == [
        SubjectEntry(
            subject="13",
            description="FICCION",
            subject_type="L0",
            aliases=("Fiction", "Novel"),
        ),
        SubjectEntry(
            subject="1402",
            description="HISTORIA",
            subject_type="L0",
            aliases=("Historical",),
        ),
    ]


def test_load_subject_rows_from_tabular_catalog_uses_description(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.tsv"
    subject_file.write_text(
        "Subject\tDescription\tSubject_Type\tAliases\n"
        "13\tFICCION\tL0\tFiction | Novel\n"
        "1402\tHISTORIA\tL0\tHistorical\n",
        encoding="utf-8",
    )

    rows = load_subject_rows(subject_file)
    subjects = load_subjects(subject_file)

    assert rows == [["FICCION", "Fiction", "Novel"], ["HISTORIA", "Historical"]]
    assert subjects == ["FICCION", "HISTORIA"]
