from unittest.mock import patch

from typer.testing import CliRunner

from book_store_assistant.cli import app

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
    assert "Fetched records: 0" in result.stdout
    assert "Resolved records: 0" in result.stdout
