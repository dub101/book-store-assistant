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
    "FieldSources",
    "ReasonCodes",
    "ReviewDetails",
]

COLUMN_WIDTHS = {
    "A": 18,
    "B": 32,
    "C": 28,
    "D": 24,
    "E": 24,
    "F": 16,
    "G": 12,
    "H": 18,
    "I": 28,
    "J": 36,
    "K": 60,
    "L": 40,
    "M": 28,
    "N": 60,
}


def _format_field_sources(field_sources: dict[str, str]) -> str | None:
    if not field_sources:
        return None

    return "; ".join(f"{field}={source}" for field, source in sorted(field_sources.items()))


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
                _format_field_sources(source_record.field_sources) if source_record is not None else None,
                ", ".join(result.reason_codes),
                "; ".join(result.review_details),
            ]
        )

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions

    for column, width in COLUMN_WIDTHS.items():
        sheet.column_dimensions[column].width = width

    for row in sheet.iter_rows(min_row=2, min_col=11, max_col=14):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    workbook.save(output_path)
