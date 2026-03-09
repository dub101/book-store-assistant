from unittest.mock import patch

from typer.testing import CliRunner

from book_store_assistant.cli import app
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
    assert "Fetched records: 1" in result.stdout
    assert "Resolved records: 0" in result.stdout
    assert "Unresolved records: 2" in result.stdout
    assert "Unresolved sources:" in result.stdout
    assert "- fetch_error: 1" in result.stdout
    assert "- google_books: 1" in result.stdout
    assert "Unresolved reasons:" in result.stdout
    assert "- FETCH_ERROR: 1" in result.stdout
    assert "- MISSING_SUBJECT: 1" in result.stdout
