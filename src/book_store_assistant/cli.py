from pathlib import Path

import typer

from book_store_assistant.pipeline.export import export_resolved_records
from book_store_assistant.pipeline.review_export import export_unresolved_results
from book_store_assistant.pipeline.service import process_isbn_file

app = typer.Typer(help="Book Store Assistant CLI.")


@app.command()
def main(
    input_path: Path,
    output: Path | None = None,
    review_output: Path | None = None,
) -> None:
    """Read ISBNs from a CSV file and report pipeline counts."""
    result = process_isbn_file(input_path)
    resolved_count = sum(1 for item in result.resolution_results if item.record is not None)
    unresolved_count = sum(1 for item in result.resolution_results if item.record is None)

    typer.echo(f"Valid ISBNs: {len(result.input_result.valid_inputs)}")
    typer.echo(f"Invalid rows: {len(result.input_result.invalid_values)}")
    typer.echo(f"Fetched records: {sum(1 for item in result.fetch_results if item.record is not None)}")
    typer.echo(f"Resolved records: {resolved_count}")
    typer.echo(f"Unresolved records: {unresolved_count}")

    if output is not None:
        export_resolved_records(result.resolution_results, output)
        typer.echo(f"Exported resolved records to {output}")

    if review_output is not None:
        export_unresolved_results(result.resolution_results, review_output)
        typer.echo(f"Exported unresolved records to {review_output}")
