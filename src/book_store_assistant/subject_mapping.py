from book_store_assistant.subjects import SUBJECTS


def has_subjects() -> bool:
    return len(SUBJECTS) > 0
