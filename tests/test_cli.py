import os
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.cli import app
from book_store_assistant.pipeline.contracts import ISBNInput
from book_store_assistant.pipeline.process_results import ProcessResult
from book_store_assistant.pipeline.results import InputReadResult
from book_store_assistant.resolution.models import RecordValidationAssessment
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult

runner = CliRunner()


def _cli_env() -> dict[str, str]:
    env = dict(os.environ)
    env["BSA_PUBLISHER_PAGE_LOOKUP_ENABLED"] = "0"
    env["BSA_RETAILER_PAGE_LOOKUP_ENABLED"] = "0"
    return env


@patch("book_store_assistant.cli.process_isbn_file")
def test_cli_main_reports_bibliographic_pipeline_counts(
    mock_process_isbn_file,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\ninvalid\n", encoding="utf-8")
    mock_process_isbn_file.return_value = ProcessResult(
        input_result=InputReadResult(
            valid_inputs=[ISBNInput(isbn="9780306406157")],
            invalid_values=["invalid"],
        ),
        fetch_results=[
            FetchResult(
                isbn="9780306406157",
                record=SourceBookRecord(
                    source_name="google_books",
                    isbn="9780306406157",
                    title="Example Title",
                    author="Example Author",
                    editorial="Example Editorial",
                ),
                errors=[],
            )
        ],
        resolution_results=[
            ResolutionResult(
                record=BibliographicRecord(
                    isbn="9780306406157",
                    title="Example Title",
                    author="Example Author",
                    editorial="Example Editorial",
                    publisher="Example Editorial",
                ),
                candidate_record=BibliographicRecord(
                    isbn="9780306406157",
                    title="Example Title",
                    author="Example Author",
                    editorial="Example Editorial",
                    publisher="Example Editorial",
                ),
                source_record=SourceBookRecord(
                    source_name="google_books",
                    isbn="9780306406157",
                ),
                validation_assessment=RecordValidationAssessment(
                    accepted=True,
                    confidence=0.96,
                ),
                errors=[],
                reason_codes=[],
                review_details=[],
            )
        ],
    )

    result = runner.invoke(app, [str(input_file)], env=_cli_env())

    assert result.exit_code == 0
    assert "Valid ISBNs: 1" in result.stdout
    assert "Invalid rows: 1" in result.stdout
    assert "Fetched records: 1" in result.stdout
    assert "Resolved records: 1" in result.stdout
    assert "Unresolved records: 0" in result.stdout
    assert "9780306406157: resolved" in result.stderr


@patch("book_store_assistant.cli.process_isbn_file")
def test_cli_main_exports_upload_review_and_handoff_outputs(
    mock_process_isbn_file,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n9780306406158\n", encoding="utf-8")
    output_file = tmp_path / "upload.xlsx"
    review_file = tmp_path / "review.xlsx"
    handoff_file = tmp_path / "handoff.jsonl"

    accepted_record = BibliographicRecord(
        isbn="9780306406157",
        title="Example Title",
        subtitle="Example Subtitle",
        author="Example Author",
        editorial="Example Editorial",
        publisher="Example Publisher",
    )
    mock_process_isbn_file.return_value = ProcessResult(
        input_result=InputReadResult(
            valid_inputs=[
                ISBNInput(isbn="9780306406157"),
                ISBNInput(isbn="9780306406158"),
            ],
            invalid_values=[],
        ),
        fetch_results=[
            FetchResult(
                isbn="9780306406157",
                record=SourceBookRecord(source_name="google_books", isbn="9780306406157"),
                errors=[],
            ),
            FetchResult(
                isbn="9780306406158",
                record=SourceBookRecord(source_name="google_books", isbn="9780306406158"),
                errors=[],
            ),
        ],
        resolution_results=[
            ResolutionResult(
                record=accepted_record,
                candidate_record=accepted_record,
                source_record=SourceBookRecord(
                    source_name="google_books",
                    isbn="9780306406157",
                    title="Example Title",
                    subtitle="Example Subtitle",
                    author="Example Author",
                    editorial="Example Editorial",
                ),
                validation_assessment=RecordValidationAssessment(
                    accepted=True,
                    confidence=0.96,
                ),
                errors=[],
                reason_codes=[],
                review_details=[],
            ),
            ResolutionResult(
                record=None,
                candidate_record=BibliographicRecord(
                    isbn="9780306406158",
                    title="Questionable Title",
                    author="Questionable Author",
                    editorial="Questionable Editorial",
                    publisher="Questionable Publisher",
                ),
                source_record=SourceBookRecord(
                    source_name="google_books",
                    isbn="9780306406158",
                    title="Questionable Title",
                    author="Questionable Author",
                    editorial="Questionable Editorial",
                ),
                validation_assessment=RecordValidationAssessment(
                    accepted=False,
                    confidence=0.42,
                    issues=["title_mismatch"],
                    explanation="Title is not well supported by the source evidence.",
                ),
                errors=["LLM validation rejected the bibliographic record."],
                reason_codes=["VALIDATION_REJECTED"],
                review_details=["Title is not well supported by the source evidence."],
            ),
        ],
    )

    result = runner.invoke(
        app,
        [
            str(input_file),
            "--output",
            str(output_file),
            "--review-output",
            str(review_file),
            "--handoff-output",
            str(handoff_file),
        ],
        env=_cli_env(),
    )

    assert result.exit_code == 0
    assert output_file.exists()
    assert review_file.exists()
    assert handoff_file.exists()
    assert "Exported upload records" in result.stdout
    assert "Exported review records" in result.stdout
    assert "Exported handoff results" in result.stdout
