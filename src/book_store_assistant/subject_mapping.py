from pathlib import Path

from book_store_assistant.subject_loader import load_subjects


DEFAULT_SUBJECTS_PATH = Path("data/reference/subjects.txt")


def get_subjects(path: Path = DEFAULT_SUBJECTS_PATH) -> list[str]:
    return load_subjects(path)


def has_subjects(path: Path = DEFAULT_SUBJECTS_PATH) -> bool:
    return len(get_subjects(path)) > 0
