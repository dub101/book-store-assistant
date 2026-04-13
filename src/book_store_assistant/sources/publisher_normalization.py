"""Normalize publisher/editorial names from ISBNdb and other sources.

ISBNdb frequently returns parent company names or distributors instead of
the specific imprint that published the book. This module provides:

1. Character normalization (fix known typos like "Debols!llo")
2. Detection of corporate/distributor names that are not real imprints
"""

import re

_CHAR_FIXES = {
    "Debols!llo": "Debolsillo",
}

_CORPORATE_NAMES = {
    "penguin random house grupo editorial",
    "penguin random house grupo editorial s.a.s.",
    "penguin random house grupo editorial (usa) llc",
    "penguin random house",
    "random house mondadori",
    "random house",
    "national geographic books",
    "planeta publishing corporation",
    "planeta publishing",
    "grupo planeta",
    "grupo planeta (gbs)",
    "harpercollins publishers",
    "simon & schuster",
    "hachette book group",
    "macmillan publishers",
    "lectorum publications",
    "lectorum publications, incorporated",
}

_CORPORATE_PATTERN = re.compile(
    r"(?:random house|penguin|national geographic|planeta publishing|"
    r"grupo planeta|harpercollins publishers|simon & schuster|"
    r"hachette book group|macmillan publishers|lectorum publications)",
    re.IGNORECASE,
)


def fix_publisher_typos(editorial: str) -> str:
    for typo, fix in _CHAR_FIXES.items():
        if typo in editorial:
            editorial = editorial.replace(typo, fix)
    return editorial


def is_corporate_name(editorial: str) -> bool:
    normalized = editorial.strip().lower()
    if normalized in _CORPORATE_NAMES:
        return True
    return bool(_CORPORATE_PATTERN.search(normalized))
