import unicodedata


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(character for character in normalized if not unicodedata.combining(character))


def _normalize_subject_text(value: str) -> str:
    normalized = _strip_accents(value)
    return " ".join(normalized.strip().casefold().replace("-", " ").split())


def select_subject(candidate: str | None, allowed_subjects: list[str]) -> str | None:
    if candidate is None:
        return None

    normalized_candidate = _normalize_subject_text(candidate)
    for subject in allowed_subjects:
        if _normalize_subject_text(subject) == normalized_candidate:
            return subject

    return None
