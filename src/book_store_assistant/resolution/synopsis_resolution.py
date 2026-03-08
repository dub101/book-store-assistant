from book_store_assistant.synopsis import format_synopsis, has_synopsis


def resolve_synopsis(synopsis: str | None, language: str | None) -> str | None:
    if not has_synopsis(synopsis):
        return None

    return format_synopsis(spanish_text=synopsis, original_text=synopsis, language=language)
