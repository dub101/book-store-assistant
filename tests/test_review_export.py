from pathlib import Path

import openpyxl

from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.models import SourceBookRecord


def test_review_rows_can_be_written_to_excel(tmp_path: Path) -> None:
    from book_store_assistant.export.review import export_review_rows

    output_file = tmp_path / "review.xlsx"
    source_record = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        title="Example Title",
        author="Example Author",
        editorial="Example Editorial",
        language="en",
    )
    results = [
        ResolutionResult(
            record=None,
            source_record=source_record,
            errors=["Synopsis is missing.", "Synopsis is not in Spanish and requires review."],
        ),
        ResolutionResult(
            record=BookRecord(
                isbn="0306406152",
                title="Resolved Title",
                author="Example Author",
                editorial="Example Editorial",
                synopsis="Resumen del libro.",
                subject="Narrativa",
            ),
            source_record=source_record,
            errors=[],
        ),
    ]

    export_review_rows(results, output_file)

    workbook = openpyxl.load_workbook(output_file)
    sheet = workbook.active

    assert sheet.cell(row=1, column=1).value == "ISBN"
    assert sheet.cell(row=1, column=3).value == "Author"
    assert sheet.cell(row=1, column=4).value == "Editorial"
    assert sheet.cell(row=1, column=6).value == "Language"
    assert sheet.cell(row=1, column=7).value == "Errors"
    assert sheet.cell(row=2, column=1).value == "9780306406157"
    assert sheet.cell(row=2, column=3).value == "Example Author"
    assert sheet.cell(row=2, column=4).value == "Example Editorial"
    assert sheet.cell(row=2, column=6).value == "en"
    assert "Synopsis is missing." in sheet.cell(row=2, column=7).value
    assert sheet.max_row == 2
