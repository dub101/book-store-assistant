from book_store_assistant.resolution.synopsis_resolution import (
    NON_SPANISH_SYNOPSIS_REVIEW_ERROR,
    get_synopsis_review_error,
    is_spanish_language,
    resolve_synopsis,
)


def test_is_spanish_language_returns_true_for_spanish_codes() -> None:
    assert is_spanish_language("es") is True
    assert is_spanish_language("spa") is True
    assert is_spanish_language(" ES ") is True


def test_is_spanish_language_returns_false_for_non_spanish_codes() -> None:
    assert is_spanish_language(None) is False
    assert is_spanish_language("en") is False


def test_resolve_synopsis_returns_none_when_missing() -> None:
    assert resolve_synopsis(None, "es") is None


def test_resolve_synopsis_returns_plain_spanish_text_for_spanish_books() -> None:
    result = resolve_synopsis("Resumen del libro.", "es")

    assert result == "Resumen del libro."


def test_resolve_synopsis_returns_plain_text_for_spa_language_code() -> None:
    result = resolve_synopsis("Resumen del libro.", "spa")

    assert result == "Resumen del libro."


def test_resolve_synopsis_returns_plain_text_when_language_is_unknown() -> None:
    result = resolve_synopsis("Resumen del libro.", None)

    assert result == "Resumen del libro."


def test_resolve_synopsis_returns_none_for_non_spanish_books() -> None:
    result = resolve_synopsis("Book description.", "en")

    assert result is None


def test_get_synopsis_review_error_returns_none_when_missing() -> None:
    assert get_synopsis_review_error(None, "es") is None


def test_get_synopsis_review_error_returns_none_for_spanish_books() -> None:
    assert get_synopsis_review_error("Resumen del libro.", "es") is None


def test_get_synopsis_review_error_returns_none_for_spa_language_code() -> None:
    assert get_synopsis_review_error("Resumen del libro.", "spa") is None


def test_get_synopsis_review_error_returns_none_when_language_is_unknown() -> None:
    assert get_synopsis_review_error("Resumen del libro.", None) is None


def test_get_synopsis_review_error_returns_review_error_for_non_spanish_books() -> None:
    result = get_synopsis_review_error("Book description.", "en")

    assert result == NON_SPANISH_SYNOPSIS_REVIEW_ERROR
