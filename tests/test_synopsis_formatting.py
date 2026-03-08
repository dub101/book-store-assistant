from book_store_assistant.synopsis import format_synopsis


def test_format_synopsis_returns_spanish_only_for_spanish_books() -> None:
    result = format_synopsis(
        spanish_text="Resumen en espanol.",
        original_text="Original text.",
        language="es",
    )

    assert result == "Resumen en espanol."


def test_format_synopsis_returns_spanish_then_original_for_non_spanish_books() -> None:
    result = format_synopsis(
        spanish_text="Resumen en espanol.",
        original_text="Original text.",
        language="en",
    )

    assert result == "Resumen en espanol.\n\nOriginal text."
