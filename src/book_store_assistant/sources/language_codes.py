LANGUAGE_CODE_MAP = {
    "spa": "es",
    "eng": "en",
}


def normalize_language_code(language: str | None) -> str | None:
    if language is None:
        return None

    normalized = language.strip().lower()
    return LANGUAGE_CODE_MAP.get(normalized, normalized or None)
