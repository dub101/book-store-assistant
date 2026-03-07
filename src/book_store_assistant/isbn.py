def normalize_isbn(raw_value: str) -> str:
    """Return an ISBN stripped to digits plus a possible trailing X."""
    value = raw_value.replace("-", "").replace(" ", "").strip().upper()
    return value


def is_valid_isbn(isbn: str) -> bool:
    """Validate ISBN-10 and ISBN-13 values."""
    if len(isbn) == 10:
        total = 0
        for index, char in enumerate(isbn):
            if char == "X" and index == 9:
                digit = 10
            elif char.isdigit():
                digit = int(char)
            else:
                return False
            total += digit * (10 - index)
        return total % 11 == 0

    if len(isbn) == 13 and isbn.isdigit():
        total = 0
        for index, char in enumerate(isbn):
            digit = int(char)
            total += digit if index % 2 == 0 else digit * 3
        return total % 10 == 0

    return False
