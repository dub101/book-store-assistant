from openpyxl.worksheet.worksheet import Worksheet

from book_store_assistant.export.schema import (
    BOOKS_HEADERS,
    BOOKS_SHEET_NAME,
    REVIEW_HEADERS,
    REVIEW_SHEET_NAME,
)

BOOKS_REQUIRED_HEADERS = (
    "ISBN",
    "Title",
    "Author",
    "Editorial",
    "Synopsis",
    "Subject",
    "SubjectCode",
)


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def validate_books_sheet(sheet: Worksheet) -> list[str]:
    errors: list[str] = []

    if sheet.title != BOOKS_SHEET_NAME:
        errors.append(
            f"Books sheet title must be '{BOOKS_SHEET_NAME}', got '{sheet.title}'."
        )

    headers = [cell.value for cell in sheet[1]]
    if headers != BOOKS_HEADERS:
        errors.append(f"Books sheet headers must be {BOOKS_HEADERS}, got {headers}.")

    if sheet.freeze_panes != "A2":
        errors.append(f"Books sheet freeze panes must be 'A2', got '{sheet.freeze_panes}'.")

    return errors


def validate_review_sheet(sheet: Worksheet) -> list[str]:
    errors: list[str] = []

    if sheet.title != REVIEW_SHEET_NAME:
        errors.append(
            f"Review sheet title must be '{REVIEW_SHEET_NAME}', got '{sheet.title}'."
        )

    headers = [cell.value for cell in sheet[1]]
    if headers != REVIEW_HEADERS:
        errors.append(f"Review sheet headers must be {REVIEW_HEADERS}, got {headers}.")

    if sheet.freeze_panes != "A2":
        errors.append(f"Review sheet freeze panes must be 'A2', got '{sheet.freeze_panes}'.")

    return errors


def validate_books_row(row: list[str | None]) -> list[str]:
    if len(row) != len(BOOKS_HEADERS):
        return [
            f"Books row must have {len(BOOKS_HEADERS)} columns, got {len(row)}."
        ]

    errors: list[str] = []

    for header in BOOKS_REQUIRED_HEADERS:
        value = row[BOOKS_HEADERS.index(header)]
        if _is_blank(value):
            errors.append(f"Books row field '{header}' is required.")

    return errors


def validate_review_row(row: list[str | None]) -> list[str]:
    if len(row) == len(REVIEW_HEADERS):
        return []

    return [
        f"Review row must have {len(REVIEW_HEADERS)} columns, got {len(row)}."
    ]
