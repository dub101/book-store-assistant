def has_synopsis(text: str | None) -> bool:
    return text is not None and bool(text.strip())


def format_synopsis(spanish_text: str, original_text: str | None, language: str | None) -> str:
    normalized_spanish = spanish_text.strip()
    normalized_original = original_text.strip() if original_text is not None else None

    if language == "es" or not normalized_original:
        return normalized_spanish

    return f"{normalized_spanish}\n\n{normalized_original}"
