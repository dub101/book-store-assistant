from book_store_assistant.resolution.synopsis_resolution import (
    get_synopsis_review_error,
    is_spanish_language,
    resolve_synopsis,
)


def test_resolve_synopsis_returns_text_when_language_is_spanish() -> None:
    assert resolve_synopsis("Una novela fascinante.", "es") == "Una novela fascinante."


def test_resolve_synopsis_accepts_spa_language_code() -> None:
    assert resolve_synopsis("Una novela fascinante.", "spa") == "Una novela fascinante."


def test_resolve_synopsis_returns_none_when_synopsis_is_missing() -> None:
    assert resolve_synopsis(None, "es") is None
    assert resolve_synopsis("", "es") is None
    assert resolve_synopsis("   ", "es") is None


def test_resolve_synopsis_returns_none_when_language_is_not_spanish() -> None:
    assert resolve_synopsis("A fascinating novel.", "en") is None


def test_resolve_synopsis_strips_whitespace() -> None:
    assert resolve_synopsis("  Una novela.  ", "es") == "Una novela."


def test_resolve_synopsis_accepts_unknown_language_when_none() -> None:
    # No language hint — accept the synopsis as-is
    assert resolve_synopsis("Una novela fascinante.", None) == "Una novela fascinante."


def test_is_spanish_language_recognises_common_codes() -> None:
    assert is_spanish_language("es") is True
    assert is_spanish_language("spa") is True
    assert is_spanish_language("ES") is True
    assert is_spanish_language("en") is False
    assert is_spanish_language(None) is False


def test_get_synopsis_review_error_returns_none_for_valid_spanish() -> None:
    assert get_synopsis_review_error("Sinopsis.", "es") is None


def test_get_synopsis_review_error_returns_error_for_non_spanish() -> None:
    error = get_synopsis_review_error("A synopsis.", "en")
    assert error is not None
    assert "Spanish" in error or "review" in error.lower()


def test_get_synopsis_review_error_returns_none_when_synopsis_is_missing() -> None:
    assert get_synopsis_review_error(None, "es") is None
    assert get_synopsis_review_error("", "en") is None
