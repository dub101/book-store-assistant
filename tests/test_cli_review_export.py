from pathlib import Path
from unittest.mock import patch

import openpyxl
from typer.testing import CliRunner

from book_store_assistant.cli import app
from book_store_assistant.config import ExecutionMode
from book_store_assistant.models import BookRecord
from book_store_assistant.pipeline.contracts import ISBNInput
from book_store_assistant.pipeline.process_results import ProcessResult
from book_store_assistant.pipeline.results import InputReadResult
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.models import SourceBookRecord

runner = CliRunner()


@patch("book_store_assistant.cli.process_isbn_file")
def test_cli_can_export_review_rows(mock_process_isbn_file, tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    review_file = tmp_path / "review.xlsx"
    expected_review_file = tmp_path / "review.rules-only.xlsx"
    input_file.write_text("9780306406157\n", encoding="utf-8")

    mock_process_isbn_file.return_value = ProcessResult(
        input_result=InputReadResult(
            valid_inputs=[ISBNInput(isbn="9780306406157")],
            invalid_values=[],
        ),
        fetch_results=[],
        resolution_results=[
            ResolutionResult(
                record=None,
                source_record=SourceBookRecord(
                    source_name="google_books",
                    isbn="9780306406157",
                    title="Example Title",
                ),
                errors=["Synopsis is missing."],
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
                source_record=None,
                errors=[],
            ),
        ],
    )

    result = runner.invoke(app, [str(input_file), "--review-output", str(review_file)])

    assert result.exit_code == 0
    workbook = openpyxl.load_workbook(expected_review_file)
    sheet = workbook.active
    assert sheet.cell(row=2, column=1).value == "9780306406157"


@patch("book_store_assistant.cli.process_isbn_file")
def test_cli_can_export_mode_specific_review_rows(
    mock_process_isbn_file,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "isbns.csv"
    review_file = tmp_path / "review.xlsx"
    expected_review_file = tmp_path / "review.ai-enriched.xlsx"
    input_file.write_text("9780306406157\n", encoding="utf-8")

    mock_process_isbn_file.return_value = ProcessResult(
        input_result=InputReadResult(
            valid_inputs=[ISBNInput(isbn="9780306406157")],
            invalid_values=[],
        ),
        fetch_results=[],
        resolution_results=[
            ResolutionResult(
                record=None,
                source_record=SourceBookRecord(
                    source_name="google_books",
                    isbn="9780306406157",
                    title="Example Title",
                ),
                errors=["Synopsis is missing."],
            ),
        ],
    )

    result = runner.invoke(
        app,
        [
            str(input_file),
            "--review-output",
            str(review_file),
            "--mode",
            ExecutionMode.AI_ENRICHED.value,
        ],
    )

    assert result.exit_code == 0
    workbook = openpyxl.load_workbook(expected_review_file)
    sheet = workbook.active
    assert sheet.cell(row=2, column=1).value == "9780306406157"
