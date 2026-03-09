from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment

from book_store_assistant.export.schema import BOOKS_HEADERS, BOOKS_SHEET_NAME
from book_store_assistant.models import BookRecord


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

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions

    for row in sheet.iter_rows(min_row=2, min_col=6, max_col=6):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    workbook.save(output_path)
