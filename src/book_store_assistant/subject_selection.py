def select_subject(candidate: str | None, allowed_subjects: list[str]) -> str | None:
    if candidate is None:
        return None

    normalized_candidate = candidate.strip().casefold()
    for subject in allowed_subjects:
        if subject.casefold() == normalized_candidate:
            return subject

    return None
