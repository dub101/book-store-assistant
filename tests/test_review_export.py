from pathlib import Path

import openpyxl

from book_store_assistant.export.schema import REVIEW_HEADERS, REVIEW_SHEET_NAME
from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.models import SourceBookRecord


def test_review_rows_can_be_written_to_excel(tmp_path: Path) -> None:
    from book_store_assistant.export.review import export_review_rows

    output_file = tmp_path / "review.xlsx"
    source_record = SourceBookRecord(
        source_name="google_books + open_library",
        isbn="9780306406157",
        title="Example Title",
        subtitle="Example Subtitle",
        author="Example Author",
        editorial="Example Editorial",
        synopsis="Book description.",
        subject="Fiction",
        language="en",
        categories=["Fiction", "Literature"],
        cover_url="https://example.com/cover.jpg",
        field_sources={
            "title": "google_books",
            "editorial": "open_library",
            "categories": "google_books + open_library",
        },
    )
    results = [
        ResolutionResult(
            record=None,
            source_record=source_record,
            errors=[
                "Synopsis is missing.",
                "Synopsis came from google_books with language 'en'.",
            ],
            reason_codes=["MISSING_SYNOPSIS"],
            review_details=["Synopsis came from google_books with language 'en'."],
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
            reason_codes=[],
            review_details=[],
        ),
    ]

    export_review_rows(results, output_file)

    workbook = openpyxl.load_workbook(output_file)
    sheet = workbook.active

    assert sheet.title == REVIEW_SHEET_NAME
    assert [cell.value for cell in sheet[1]] == REVIEW_HEADERS
    assert sheet.cell(row=2, column=1).value == "9780306406157"
    assert sheet.cell(row=2, column=11).value == "Book description."
    assert "categories=google_books + open_library" in sheet.cell(row=2, column=12).value
    assert sheet.cell(row=2, column=13).value == "MISSING_SYNOPSIS"
    assert (
        "Synopsis came from google_books with language 'en'."
        in sheet.cell(row=2, column=14).value
    )
    assert sheet.cell(row=2, column=11).alignment.wrap_text is True
    assert sheet.cell(row=2, column=12).alignment.wrap_text is True
    assert sheet.cell(row=2, column=13).alignment.wrap_text is True
    assert sheet.cell(row=2, column=14).alignment.wrap_text is True
    assert sheet.freeze_panes == "A2"
    assert sheet.auto_filter.ref == "A1:N2"
    assert sheet.max_row == 2
