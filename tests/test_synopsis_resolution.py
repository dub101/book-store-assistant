from book_store_assistant.resolution.synopsis_resolution import resolve_synopsis


def test_resolve_synopsis_returns_none_when_missing() -> None:
    assert resolve_synopsis(None, "es") is None


def test_resolve_synopsis_returns_plain_spanish_text_for_spanish_books() -> None:
    result = resolve_synopsis("Resumen del libro.", "es")

    assert result == "Resumen del libro."


def test_resolve_synopsis_duplicates_text_for_non_spanish_books_for_now() -> None:
    result = resolve_synopsis("Book description.", "en")

    assert result == "Book description.\n\nBook description."
