from book_store_assistant.synopsis import has_synopsis


NON_SPANISH_SYNOPSIS_REVIEW_ERROR = "Synopsis is not in Spanish and requires review."
SPANISH_LANGUAGE_CODES = {"es", "spa"}


def is_spanish_language(language: str | None) -> bool:
    if language is None:
        return False

    return language.strip().lower() in SPANISH_LANGUAGE_CODES


def resolve_synopsis(synopsis: str | None, language: str | None) -> str | None:
    if not has_synopsis(synopsis):
        return None

    if language is not None and not is_spanish_language(language):
        return None

    return synopsis.strip()


def get_synopsis_review_error(synopsis: str | None, language: str | None) -> str | None:
    if not has_synopsis(synopsis):
        return None

    if language is not None and not is_spanish_language(language):
        return NON_SPANISH_SYNOPSIS_REVIEW_ERROR

    return None
