from pathlib import Path

from book_store_assistant.subject_loader import load_subject_rows, load_subjects


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
