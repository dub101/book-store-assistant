from book_store_assistant.subject_selection import select_subject


def _expand_candidates(candidate: str) -> list[str]:
    expanded = [candidate]

    for separator in ("/", ","):
        parts: list[str] = []
        for item in expanded:
            parts.extend(item.split(separator))
        expanded = parts

    return [item.strip() for item in expanded if item.strip()]


def resolve_subject(candidates: list[str], allowed_subjects: list[str]) -> str | None:
    for candidate in candidates:
        for expanded_candidate in _expand_candidates(candidate):
            subject = select_subject(expanded_candidate, allowed_subjects)
            if subject is not None:
                return subject

    return None
