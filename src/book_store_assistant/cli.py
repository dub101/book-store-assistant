from collections import Counter
from pathlib import Path

import typer

from book_store_assistant.pipeline.export import export_resolved_records
from book_store_assistant.pipeline.input import read_isbn_inputs
from book_store_assistant.pipeline.review_export import export_unresolved_results
from book_store_assistant.pipeline.service import process_isbn_file
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.results import FetchResult

app = typer.Typer(help="Book Store Assistant CLI.")


def _summarize_fetch_result(result: FetchResult) -> str:
    if result.record is not None and result.errors:
        return f"{result.isbn}: metadata fetched with source errors"
    if result.record is not None:
        return f"{result.isbn}: metadata fetched"
    if result.errors:
        return f"{result.isbn}: fetch failed"
    return f"{result.isbn}: no metadata found"


def _summarize_resolution_result(result: ResolutionResult) -> str:
    if result.record is not None:
        return f"{result.record.isbn}: resolved"

    if result.source_record is not None:
        isbn = result.source_record.isbn
    else:
        isbn = "unknown-isbn"

    if result.reason_codes:
        reason_codes = ", ".join(result.reason_codes)
        return f"{isbn}: review ({reason_codes})"

    return f"{isbn}: review"


@app.command()
def main(
    input_path: Path,
    output: Path | None = None,
    review_output: Path | None = None,
) -> None:
    """Read ISBNs from a CSV file and report pipeline counts."""
    input_preview = read_isbn_inputs(input_path)

    if input_preview.valid_inputs:
        with typer.progressbar(
            length=len(input_preview.valid_inputs),
            label="Consulting ISBNs",
        ) as progress:

            def on_fetch_start(index: int, total: int, isbn: str) -> None:
                typer.echo(f"Consulting ISBN {index}/{total}: {isbn}", err=True)

            def on_fetch_complete(index: int, total: int, result: FetchResult) -> None:
                progress.update(1)
                typer.echo(_summarize_fetch_result(result), err=True)

            result = process_isbn_file(
                input_path,
                on_fetch_start=on_fetch_start,
                on_fetch_complete=on_fetch_complete,
            )
    else:
        result = process_isbn_file(input_path)

    for resolution_result in result.resolution_results:
        typer.echo(_summarize_resolution_result(resolution_result), err=True)

    resolved_count = sum(1 for item in result.resolution_results if item.record is not None)
    unresolved_results = [item for item in result.resolution_results if item.record is None]
    unresolved_count = len(unresolved_results)
    fetched_count = sum(1 for item in result.fetch_results if item.record is not None)

    typer.echo(f"Valid ISBNs: {len(result.input_result.valid_inputs)}")
    typer.echo(f"Invalid rows: {len(result.input_result.invalid_values)}")

    if result.input_result.invalid_values:
        typer.echo("Invalid values:")
        for invalid_value in result.input_result.invalid_values:
            typer.echo(f"- {invalid_value}")

    typer.echo(f"Fetched records: {fetched_count}")
    typer.echo(f"Resolved records: {resolved_count}")
    typer.echo(f"Unresolved records: {unresolved_count}")

    if unresolved_results:
        source_counts = Counter(
            unresolved_result.source_record.source_name
            for unresolved_result in unresolved_results
            if unresolved_result.source_record is not None
        )
        reason_counts = Counter(
            reason_code
            for unresolved_result in unresolved_results
            for reason_code in unresolved_result.reason_codes
        )

        if source_counts:
            typer.echo("Unresolved sources:")
            for source_name, count in sorted(source_counts.items()):
                typer.echo(f"- {source_name}: {count}")

        typer.echo("Unresolved reasons:")
        for reason_code, count in sorted(reason_counts.items()):
            typer.echo(f"- {reason_code}: {count}")

    if output is not None:
        export_resolved_records(result.resolution_results, output)
        typer.echo(f"Exported resolved records to {output}")

    if review_output is not None:
        export_unresolved_results(result.resolution_results, review_output)
        typer.echo(f"Exported unresolved records to {review_output}")
