from typer.testing import CliRunner

from book_store_assistant.cli import app

runner = CliRunner()


def test_cli_main_reports_valid_and_invalid_counts(tmp_path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\ninvalid\n", encoding="utf-8")

    result = runner.invoke(app, [str(input_file)])

    assert result.exit_code == 0
    assert "Valid ISBNs: 1" in result.stdout
    assert "Invalid rows: 1" in result.stdout
