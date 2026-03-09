from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment

from book_store_assistant.resolution.results import ResolutionResult


HEADERS = [
    "ISBN",
    "Title",
    "Subtitle",
    "Author",
    "Editorial",
    "Source",
    "Language",
    "Subject",
    "Categories",
    "CoverURL",
    "Synopsis",
    "Errors",
]


def export_review_rows(results: list[ResolutionResult], output_path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Review"
    sheet.append(HEADERS)

    for result in results:
        if result.record is not None:
            continue

        source_record = result.source_record
        sheet.append(
            [
                source_record.isbn if source_record is not None else None,
                source_record.title if source_record is not None else None,
                source_record.subtitle if source_record is not None else None,
                source_record.author if source_record is not None else None,
                source_record.editorial if source_record is not None else None,
                source_record.source_name if source_record is not None else None,
                source_record.language if source_record is not None else None,
                source_record.subject if source_record is not None else None,
                ", ".join(source_record.categories) if source_record is not None else None,
                str(source_record.cover_url) if source_record is not None and source_record.cover_url else None,
                source_record.synopsis if source_record is not None else None,
                "; ".join(result.errors),
            ]
        )

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions

    for row in sheet.iter_rows(min_row=2, min_col=11, max_col=12):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    workbook.save(output_path)
