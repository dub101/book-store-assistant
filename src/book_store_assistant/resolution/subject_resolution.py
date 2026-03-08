from book_store_assistant.subject_selection import select_subject


def resolve_subject(candidates: list[str], allowed_subjects: list[str]) -> str | None:
    for candidate in candidates:
        subject = select_subject(candidate, allowed_subjects)
        if subject is not None:
            return subject

    return None
