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


def test_get_subjects_filters_non_book_subject_types_by_default(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.tsv"
    subject_file.write_text(
        "Subject\tDescription\tSubject_Type\n"
        "22\tPELUCHES Y TITERES\tP0\n"
        "13\tFICCION\tL0\n",
        encoding="utf-8",
    )

    subjects = subject_mapping.get_subjects(subject_file)

    assert subjects == ["FICCION"]


def test_get_subject_rows_includes_aliases_for_tabular_catalog(tmp_path: Path) -> None:
    subject_file = tmp_path / "subjects.tsv"
    subject_file.write_text(
        "Subject\tDescription\tSubject_Type\tAliases\n"
        "1301\tLITERATURA Y NOVELA\tL0\tRomance literature | Literature\n",
        encoding="utf-8",
    )

    rows = subject_mapping.get_subject_rows(subject_file)

    assert rows == [["LITERATURA Y NOVELA", "Romance literature", "Literature"]]
