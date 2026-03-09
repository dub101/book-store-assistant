from pathlib import Path

import openpyxl

from book_store_assistant.export.schema import BOOKS_HEADERS, BOOKS_SHEET_NAME
from book_store_assistant.export.workbook import apply_sheet_basics
from book_store_assistant.models import BookRecord
from book_store_assistant.validation.export import validate_books_sheet


def export_books(records: list[BookRecord], output_path: Path) -> None:
    """Export book records to an Excel file."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = BOOKS_SHEET_NAME
    sheet.append(BOOKS_HEADERS)

    for record in records:
        sheet.append(
            [
                record.isbn,
                record.title,
                record.subtitle,
                record.author,
                record.editorial,
                record.synopsis,
                record.subject,
                str(record.cover_url) if record.cover_url else None,
            ]
        )

    apply_sheet_basics(
        sheet,
        freeze_panes="A2",
        wrap_columns=(6, 6),
    )

    validation_errors = validate_books_sheet(sheet)
    if validation_errors:
        joined_errors = "; ".join(validation_errors)
        raise ValueError(f"Invalid books export sheet: {joined_errors}")

    workbook.save(output_path)
