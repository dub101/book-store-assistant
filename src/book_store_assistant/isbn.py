# Registration-group prefixes (after stripping EAN 978/979), longest first.
_GROUP_PREFIXES: list[tuple[str, str]] = [
    ("99954", "BO"),
    ("99922", "GT"),
    ("9972", "PE"),
    ("9974", "UY"),
    ("9978", "EC"),
    ("9968", "CR"),
    ("9962", "PA"),
    ("612", "PE"),
    ("607", "MX"),
    ("968", "MX"),
    ("970", "MX"),
    ("950", "AR"),
    ("987", "AR"),
    ("958", "CO"),
    ("956", "CL"),
    ("980", "VE"),
    ("84", "ES"),
    ("85", "BR"),
    ("65", "BR"),
]
# Sort descending by prefix length so longest match wins.
_GROUP_PREFIXES.sort(key=lambda pair: len(pair[0]), reverse=True)


def registration_group(isbn: str) -> str | None:
    """Return the 2-letter country code for an ISBN-13's registration group.

    Strips the EAN prefix (978/979) and checks the remaining digits against
    known Spanish-language and Latin-American national-agency prefixes.
    Returns ``None`` for ISBN-10 values or unknown groups.
    """
    digits = isbn.replace("-", "").replace(" ", "").strip()
    if len(digits) != 13 or not digits.isdigit():
        return None

    ean_prefix = digits[:3]
    if ean_prefix not in ("978", "979"):
        return None

    body = digits[3:]  # registration group + registrant + publication + check
    for prefix, country in _GROUP_PREFIXES:
        if body.startswith(prefix):
            return country
    return None


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
