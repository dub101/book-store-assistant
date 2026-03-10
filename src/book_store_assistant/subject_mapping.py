from pathlib import Path

from book_store_assistant.subject_loader import (
    load_subject_entries,
    load_subject_rows,
    load_subjects,
)
from book_store_assistant.subjects import SubjectEntry

DEFAULT_SUBJECTS_PATH = Path("data/reference/subjects.tsv")
BOOK_SUBJECT_TYPES = frozenset({"L0"})


def _filter_subject_entries(
    entries: list[SubjectEntry],
    allowed_subject_types: frozenset[str] | None,
) -> list[SubjectEntry]:
    if allowed_subject_types is None:
        return entries

    return [
        entry
        for entry in entries
        if not entry.subject_type or entry.subject_type in allowed_subject_types
    ]


def get_subject_entries(
    path: Path = DEFAULT_SUBJECTS_PATH,
    allowed_subject_types: frozenset[str] | None = BOOK_SUBJECT_TYPES,
) -> list[SubjectEntry]:
    return _filter_subject_entries(
        load_subject_entries(path),
        allowed_subject_types,
    )


def find_subject_entry_by_description(
    description: str,
    path: Path = DEFAULT_SUBJECTS_PATH,
    allowed_subject_types: frozenset[str] | None = BOOK_SUBJECT_TYPES,
) -> SubjectEntry | None:
    normalized_description = description.strip().casefold()
    for entry in get_subject_entries(path, allowed_subject_types):
        if entry.description.strip().casefold() == normalized_description:
            return entry

    return None


def get_subject_rows(
    path: Path = DEFAULT_SUBJECTS_PATH,
    allowed_subject_types: frozenset[str] | None = BOOK_SUBJECT_TYPES,
) -> list[list[str]]:
    entries = get_subject_entries(path, allowed_subject_types)
    if entries:
        return [[entry.description, *entry.aliases] for entry in entries]

    return load_subject_rows(path)


def get_subjects(
    path: Path = DEFAULT_SUBJECTS_PATH,
    allowed_subject_types: frozenset[str] | None = BOOK_SUBJECT_TYPES,
) -> list[str]:
    entries = get_subject_entries(path, allowed_subject_types)
    if entries:
        return [entry.description for entry in entries]

    return load_subjects(path)


def has_subjects(
    path: Path = DEFAULT_SUBJECTS_PATH,
    allowed_subject_types: frozenset[str] | None = BOOK_SUBJECT_TYPES,
) -> bool:
    return len(get_subjects(path, allowed_subject_types)) > 0
