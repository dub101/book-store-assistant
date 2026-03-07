from typer.testing import CliRunner

from book_store_assistant.cli import app

runner = CliRunner()


def test_cli_main_outputs_ready_message() -> None:
    result = runner.invoke(app, ["main"])

    assert result.exit_code == 0
    assert "Book Store Assistant CLI is ready." in result.stdout
