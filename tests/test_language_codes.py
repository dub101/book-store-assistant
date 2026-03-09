from book_store_assistant.sources.language_codes import normalize_language_code


def test_normalize_language_code_returns_none_for_none() -> None:
    assert normalize_language_code(None) is None


def test_normalize_language_code_maps_known_codes() -> None:
    assert normalize_language_code("spa") == "es"
    assert normalize_language_code("eng") == "en"


def test_normalize_language_code_normalizes_case_and_whitespace() -> None:
    assert normalize_language_code(" SPA ") == "es"


def test_normalize_language_code_keeps_unknown_codes() -> None:
    assert normalize_language_code("fre") == "fre"


def test_normalize_language_code_returns_none_for_blank_strings() -> None:
    assert normalize_language_code("   ") is None
