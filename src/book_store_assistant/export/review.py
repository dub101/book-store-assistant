from pathlib import Path

import openpyxl

from book_store_assistant.export.schema import (
    REVIEW_COLUMN_WIDTHS,
    REVIEW_HEADERS,
    REVIEW_SHEET_NAME,
)
from book_store_assistant.export.workbook import apply_sheet_basics
from book_store_assistant.resolution.results import ResolutionResult


def _format_field_sources(field_sources: dict[str, str]) -> str | None:
    if not field_sources:
        return None

    return "; ".join(f"{field}={source}" for field, source in sorted(field_sources.items()))


def export_review_rows(results: list[ResolutionResult], output_path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = REVIEW_SHEET_NAME
    sheet.append(REVIEW_HEADERS)

    for result in results:
        if result.record is not None:
            continue

        source_record = result.source_record
        cover_url = (
            str(source_record.cover_url)
            if source_record is not None and source_record.cover_url
            else None
        )
        field_sources = (
            _format_field_sources(source_record.field_sources)
            if source_record is not None
            else None
        )
        categories = ", ".join(source_record.categories) if source_record is not None else None

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
                categories,
                cover_url,
                source_record.synopsis if source_record is not None else None,
                field_sources,
                ", ".join(result.reason_codes),
                "; ".join(result.review_details),
            ]
        )

    apply_sheet_basics(
        sheet,
        freeze_panes="A2",
        column_widths=REVIEW_COLUMN_WIDTHS,
        wrap_columns=(11, 14),
    )

    workbook.save(output_path)
