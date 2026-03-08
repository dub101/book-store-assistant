from pathlib import Path

import typer

from book_store_assistant.pipeline.service import process_isbn_file

app = typer.Typer(help="Book Store Assistant CLI.")


@app.command()
def main(input_path: Path) -> None:
    """Read ISBNs from a CSV file and report pipeline counts."""
    result = process_isbn_file(input_path)
    typer.echo(f"Valid ISBNs: {len(result.input_result.valid_inputs)}")
    typer.echo(f"Invalid rows: {len(result.input_result.invalid_values)}")
    typer.echo(f"Fetched records: {sum(1 for item in result.fetch_results if item.record is not None)}")
    typer.echo(f"Resolved records: {sum(1 for item in result.resolution_results if item.record is not None)}")
