import csv
import unicodedata
from pathlib import Path

from book_store_assistant.subjects import SubjectEntry


def _normalize_column_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    stripped = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return stripped.strip().casefold()


def _read_non_empty_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _is_tabular_subject_catalog(lines: list[str]) -> bool:
    if not lines:
        return False

    first_columns = [_normalize_column_name(value) for value in lines[0].split("\t")]
    return len(first_columns) >= 3 and first_columns[:3] in (
        ["subject", "description", "subject_type"],
        ["materia", "descripcion", "tipo"],
    )


def _load_legacy_subject_rows(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []

    for line in lines:
        parts = [part.strip() for part in line.split("|")]
        values = [part for part in parts if part]
        if values:
            rows.append(values)

    return rows


def _load_tabular_subject_entries(path: Path) -> list[SubjectEntry]:
    entries: list[SubjectEntry] = []

    with path.open(newline="", encoding="utf-8") as subject_file:
        reader = csv.reader(subject_file, delimiter="\t")
        header = next(reader, None)
        if header is None:
            return []

        normalized_header = [_normalize_column_name(value) for value in header]
        subject_index = (
            normalized_header.index("subject")
            if "subject" in normalized_header
            else normalized_header.index("materia")
        )
        description_index = (
            normalized_header.index("description")
            if "description" in normalized_header
            else normalized_header.index("descripcion")
        )
        subject_type_index = (
            normalized_header.index("subject_type")
            if "subject_type" in normalized_header
            else normalized_header.index("tipo")
        )

        for row in reader:
            if not row or not any(value.strip() for value in row):
                continue

            subject = row[subject_index].strip()
            description = row[description_index].strip()
            subject_type = row[subject_type_index].strip()

            if not subject or not description:
                continue

            entries.append(
                SubjectEntry(
                    subject=subject,
                    description=description,
                    subject_type=subject_type,
                )
            )

    return entries


def load_subject_entries(path: Path) -> list[SubjectEntry]:
    lines = _read_non_empty_lines(path)
    if not lines:
        return []

    if _is_tabular_subject_catalog(lines):
        return _load_tabular_subject_entries(path)

    return [
        SubjectEntry(subject=row[0], description=row[0], subject_type="")
        for row in _load_legacy_subject_rows(lines)
    ]


def load_subject_rows(path: Path) -> list[list[str]]:
    lines = _read_non_empty_lines(path)
    if not lines:
        return []

    if _is_tabular_subject_catalog(lines):
        return [[entry.description] for entry in load_subject_entries(path)]

    return _load_legacy_subject_rows(lines)


def load_subjects(path: Path) -> list[str]:
    return [entry.description for entry in load_subject_entries(path)]
