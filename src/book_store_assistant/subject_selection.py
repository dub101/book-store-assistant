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


def _contains_normalized_phrase(candidate: str, value: str) -> bool:
    candidate_words = candidate.split()
    value_words = value.split()

    if len(value_words) > len(candidate_words):
        return False

    for index in range(len(candidate_words) - len(value_words) + 1):
        if candidate_words[index : index + len(value_words)] == value_words:
            return True

    return False


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

    for row in allowed_subject_rows:
        canonical_subject = row[0]
        for value in row:
            normalized_value = _normalize_subject_text(value)
            if _contains_normalized_phrase(normalized_candidate, normalized_value):
                return canonical_subject

    return None
