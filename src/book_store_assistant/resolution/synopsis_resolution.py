SPANISH_LANGUAGE_CODES = {"es", "spa"}


def is_spanish_language(language: str | None) -> bool:
    if language is None:
        return False
    return language.strip().lower() in SPANISH_LANGUAGE_CODES


def resolve_synopsis(synopsis: str | None, language: str | None) -> str | None:
    if not synopsis or not synopsis.strip():
        return None
    if language is not None and not is_spanish_language(language):
        return None
    return synopsis.strip()
