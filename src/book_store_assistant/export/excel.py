from pathlib import Path

import openpyxl

from book_store_assistant.models import BookRecord


HEADERS = [
    "ISBN",
    "Title",
    "Subtitle",
    "Author",
    "Editorial",
    "Synopsis",
    "Subject",
    "CoverURL",
]


def export_books(records: list[BookRecord], output_path: Path) -> None:
    """Export book records to an Excel file."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)

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

    workbook.save(output_path)
