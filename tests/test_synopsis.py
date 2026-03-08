from book_store_assistant.synopsis import has_synopsis


def test_has_synopsis_returns_true_for_non_empty_text() -> None:
    assert has_synopsis("Resumen del libro.") is True


def test_has_synopsis_returns_false_for_blank_text() -> None:
    assert has_synopsis("   ") is False
