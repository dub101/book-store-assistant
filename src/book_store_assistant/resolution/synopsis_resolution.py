from book_store_assistant.synopsis import has_synopsis


NON_SPANISH_SYNOPSIS_REVIEW_ERROR = "Synopsis is not in Spanish and requires review."


def resolve_synopsis(synopsis: str | None, language: str | None) -> str | None:
    if not has_synopsis(synopsis):
        return None

    if language and language != "es":
        return None

    return synopsis.strip()


def get_synopsis_review_error(synopsis: str | None, language: str | None) -> str | None:
    if not has_synopsis(synopsis):
        return None

    if language and language != "es":
        return NON_SPANISH_SYNOPSIS_REVIEW_ERROR

    return None
