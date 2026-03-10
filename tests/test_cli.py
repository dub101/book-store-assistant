from unittest.mock import patch

from typer.testing import CliRunner

from book_store_assistant.cli import app
from book_store_assistant.config import ExecutionMode
from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult

runner = CliRunner()


@patch("book_store_assistant.pipeline.service.fetch_all")
def test_cli_main_reports_pipeline_counts(mock_fetch_all, tmp_path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\ninvalid\n", encoding="utf-8")
    mock_fetch_all.return_value = []

    result = runner.invoke(app, [str(input_file)])

    assert result.exit_code == 0
    assert "Execution mode: rules-only" in result.stdout
    assert "Valid ISBNs: 1" in result.stdout
    assert "Invalid rows: 1" in result.stdout
    assert "Invalid values:" in result.stdout
    assert "- invalid" in result.stdout
    assert "Fetched records: 0" in result.stdout
    assert "Resolved records: 0" in result.stdout
    assert "Unresolved records: 0" in result.stdout


@patch("book_store_assistant.pipeline.service.resolve_all")
@patch("book_store_assistant.pipeline.service.fetch_all")
def test_cli_main_reports_unresolved_reason_counts(
    mock_fetch_all,
    mock_resolve_all,
    tmp_path,
) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n9780306406158\n", encoding="utf-8")

    mock_fetch_all.return_value = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Example Title",
            ),
            errors=["google_books: No Google Books match found."],
        ),
        FetchResult(
            isbn="9780306406158",
            record=None,
            errors=["open_library: Timeout"],
        ),
    ]
    mock_resolve_all.return_value = [
        ResolutionResult(
            record=None,
            source_record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Example Title",
            ),
            errors=["Subject is missing."],
            reason_codes=["MISSING_SUBJECT"],
            review_details=["No source supplied subject or usable categories."],
        ),
        ResolutionResult(
            record=None,
            source_record=SourceBookRecord(
                source_name="fetch_error",
                isbn="9780306406158",
            ),
            errors=["open_library: Timeout"],
            reason_codes=["FETCH_ERROR"],
            review_details=["open_library: Timeout"],
        ),
    ]

    result = runner.invoke(app, [str(input_file)])

    assert result.exit_code == 0
    assert "9780306406157: review (MISSING_SUBJECT)" in result.stderr
    assert "9780306406158: review (FETCH_ERROR)" in result.stderr
    assert "Fetched records: 1" in result.stdout
    assert "Resolved records: 0" in result.stdout
    assert "Unresolved records: 2" in result.stdout
    assert "Unresolved sources:" in result.stdout
    assert "- fetch_error: 1" in result.stdout
    assert "- google_books: 1" in result.stdout
    assert "Unresolved reasons:" in result.stdout
    assert "- FETCH_ERROR: 1" in result.stdout
    assert "- MISSING_SUBJECT: 1" in result.stdout


@patch("book_store_assistant.pipeline.service.resolve_all")
@patch("book_store_assistant.pipeline.service.fetch_all")
def test_cli_main_reports_final_resolution_statuses(
    mock_fetch_all,
    mock_resolve_all,
    tmp_path,
) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n9780306406158\n", encoding="utf-8")

    mock_fetch_all.return_value = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Resolved Title",
            ),
            errors=[],
        ),
        FetchResult(
            isbn="9780306406158",
            record=SourceBookRecord(
                source_name="open_library",
                isbn="9780306406158",
                title="Needs Review",
            ),
            errors=[],
        ),
    ]
    mock_resolve_all.return_value = [
        ResolutionResult(
            record=BookRecord(
                isbn="9780306406157",
                title="Resolved Title",
                author="Example Author",
                editorial="Example Editorial",
                synopsis="Resumen del libro.",
                subject="FICCION",
            ),
            source_record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
            ),
            errors=[],
            reason_codes=[],
            review_details=[],
        ),
        ResolutionResult(
            record=None,
            source_record=SourceBookRecord(
                source_name="open_library",
                isbn="9780306406158",
            ),
            errors=["Synopsis is missing."],
            reason_codes=["MISSING_SYNOPSIS", "MISSING_SUBJECT"],
            review_details=[
                "No source supplied synopsis.",
                "No source supplied subject or usable categories.",
            ],
        ),
    ]

    result = runner.invoke(app, [str(input_file)])

    assert result.exit_code == 0
    assert "9780306406157: resolved" in result.stderr
    assert "9780306406158: review (MISSING_SYNOPSIS, MISSING_SUBJECT)" in result.stderr


@patch("book_store_assistant.cli.process_isbn_file")
def test_cli_main_passes_execution_mode_to_pipeline(mock_process_isbn_file, tmp_path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")
    mock_process_isbn_file.return_value.resolution_results = []
    mock_process_isbn_file.return_value.input_result.valid_inputs = []
    mock_process_isbn_file.return_value.input_result.invalid_values = []
    mock_process_isbn_file.return_value.fetch_results = []

    result = runner.invoke(app, [str(input_file), "--mode", ExecutionMode.AI_ENRICHED.value])

    assert result.exit_code == 0
    mock_process_isbn_file.assert_called_once()
    assert mock_process_isbn_file.call_args.kwargs["mode"] == ExecutionMode.AI_ENRICHED
    assert "Execution mode: ai-enriched" in result.stdout
