from pathlib import Path

import book_store_assistant.subject_mapping as subject_mapping


def test_has_subjects_returns_true_when_reference_file_has_values(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.tsv"
    subject_file.write_text(
        "Subject\tDescription\tSubject_Type\n"
        "13\tFICCION\tL0\n",
        encoding="utf-8",
    )

    assert subject_mapping.has_subjects(subject_file) is True
