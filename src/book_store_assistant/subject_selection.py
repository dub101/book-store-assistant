import unicodedata


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(character for character in normalized if not unicodedata.combining(character))


def _normalize_subject_text(value: str) -> str:
    normalized = _strip_accents(value)
    return " ".join(normalized.strip().casefold().replace("-", " ").split())


def _normalize_subject_rows(allowed_subjects: list[str] | list[list[str]]) -> list[list[str]]:
    if not allowed_subjects:
        return []

    first_item = allowed_subjects[0]
    if isinstance(first_item, str):
        return [[subject] for subject in allowed_subjects]

    return allowed_subjects


def select_subject(candidate: str | None, allowed_subjects: list[str] | list[list[str]]) -> str | None:
    if candidate is None:
        return None

    normalized_candidate = _normalize_subject_text(candidate)
    allowed_subject_rows = _normalize_subject_rows(allowed_subjects)

    for row in allowed_subject_rows:
        canonical_subject = row[0]
        for value in row:
            if _normalize_subject_text(value) == normalized_candidate:
                return canonical_subject

    return None
