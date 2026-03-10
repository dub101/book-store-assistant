from pathlib import Path

import openpyxl

from book_store_assistant.export.rows import build_review_row
from book_store_assistant.export.schema import (
    REVIEW_COLUMN_WIDTHS,
    REVIEW_HEADERS,
    REVIEW_SHEET_NAME,
)
from book_store_assistant.export.workbook import apply_sheet_basics
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.validation.export import (
    validate_review_row,
    validate_review_sheet,
)


def export_review_rows(results: list[ResolutionResult], output_path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = REVIEW_SHEET_NAME
    sheet.append(REVIEW_HEADERS)

    for result in results:
        if result.record is not None:
            continue

        row = build_review_row(result)
        row_errors = validate_review_row(row)
        if row_errors:
            joined_errors = "; ".join(row_errors)
            raise ValueError(f"Invalid review export row: {joined_errors}")

        sheet.append(row)

    apply_sheet_basics(
        sheet,
        freeze_panes="A2",
        column_widths=REVIEW_COLUMN_WIDTHS,
        wrap_columns=(13, 23),
    )

    validation_errors = validate_review_sheet(sheet)
    if validation_errors:
        joined_errors = "; ".join(validation_errors)
        raise ValueError(f"Invalid review export sheet: {joined_errors}")

    workbook.save(output_path)
