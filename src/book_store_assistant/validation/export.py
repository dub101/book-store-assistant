from openpyxl.worksheet.worksheet import Worksheet

from book_store_assistant.export.schema import BOOKS_HEADERS, BOOKS_SHEET_NAME


def validate_books_sheet(sheet: Worksheet) -> list[str]:
    errors: list[str] = []

    if sheet.title != BOOKS_SHEET_NAME:
        errors.append(
            f"Books sheet title must be '{BOOKS_SHEET_NAME}', got '{sheet.title}'."
        )

    headers = [cell.value for cell in sheet[1]]
    if headers != BOOKS_HEADERS:
        errors.append(
            f"Books sheet headers must be {BOOKS_HEADERS}, got {headers}."
        )

    if sheet.freeze_panes != "A2":
        errors.append(f"Books sheet freeze panes must be 'A2', got '{sheet.freeze_panes}'.")

    return errors
