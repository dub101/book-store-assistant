def _normalize_subject_text(value: str) -> str:
    return " ".join(value.strip().casefold().replace("-", " ").split())


def select_subject(candidate: str | None, allowed_subjects: list[str]) -> str | None:
    if candidate is None:
        return None

    normalized_candidate = _normalize_subject_text(candidate)
    for subject in allowed_subjects:
        if _normalize_subject_text(subject) == normalized_candidate:
            return subject

    return None
