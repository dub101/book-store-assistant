from pathlib import Path

from book_store_assistant.subject_loader import load_subjects


def test_load_subjects_reads_non_empty_lines(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.txt"
    subject_file.write_text("Narrativa\n\nHistoria\n", encoding="utf-8")

    subjects = load_subjects(subject_file)

    assert subjects == ["Narrativa", "Historia"]
