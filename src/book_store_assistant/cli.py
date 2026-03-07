from pathlib import Path

import typer

from book_store_assistant.pipeline.service import process_isbn_file

app = typer.Typer(help="Book Store Assistant CLI.")


@app.command()
def main(input_path: Path) -> None:
    """Read ISBNs from a CSV file and report basic validation results."""
    valid_inputs, invalid_values = process_isbn_file(input_path)
    typer.echo(f"Valid ISBNs: {len(valid_inputs)}")
    typer.echo(f"Invalid rows: {len(invalid_values)}")
