def has_synopsis(text: str | None) -> bool:
    return text is not None and bool(text.strip())
