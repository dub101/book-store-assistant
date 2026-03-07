from book_store_assistant.isbn import is_valid_isbn, normalize_isbn


def test_normalize_isbn_removes_spaces_and_hyphens() -> None:
    assert normalize_isbn("978-1-4028 9462-6") == "9781402894626"


def test_is_valid_isbn_accepts_valid_isbn_13() -> None:
    assert is_valid_isbn("9780306406157") is True


def test_is_valid_isbn_accepts_valid_isbn_10() -> None:
    assert is_valid_isbn("0306406152") is True


def test_is_valid_isbn_rejects_invalid_value() -> None:
    assert is_valid_isbn("9780306406158") is False
