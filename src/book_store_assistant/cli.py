from collections import Counter
from pathlib import Path

import typer

from book_store_assistant.bibliographic.export import (
    export_handoff_results,
    export_review_rows,
    export_upload_records,
)
from book_store_assistant.pipeline.input import read_isbn_inputs
from book_store_assistant.pipeline.service import process_isbn_file
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.results import FetchResult

app = typer.Typer(help="Book Store Assistant CLI.")


def _default_handoff_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}.handoff.jsonl")


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


def _count_source_issue_codes(fetch_results: list[FetchResult]) -> Counter[str]:
    return Counter(
        issue_code
        for fetch_result in fetch_results
        for issue_code in fetch_result.issue_codes
    )


def _count_first_material_gain_stages(
    resolution_results: list[ResolutionResult],
) -> Counter[str]:
    first_material_gain_stages: list[str] = []
    for result in resolution_results:
        first_material_gain_stage = result.path_summary.get(
            "first_material_gain_stage"
        )
        if isinstance(first_material_gain_stage, str):
            first_material_gain_stages.append(first_material_gain_stage)
    return Counter(first_material_gain_stages)


@app.command()
def main(
    input_path: Path,
    output: Path | None = None,
    review_output: Path | None = None,
    handoff_output: Path | None = None,
) -> None:
    """Read ISBNs from a CSV file and build Stage 1 bibliographic outputs."""
    input_preview = read_isbn_inputs(input_path)

    if input_preview.valid_inputs:
        with typer.progressbar(
            length=len(input_preview.valid_inputs),
            label="Consulting ISBNs",
        ) as fetch_progress:

            def on_fetch_start(index: int, total: int, isbn: str) -> None:
                typer.echo(f"Consulting ISBN {index}/{total}: {isbn}", err=True)

            def on_fetch_complete(index: int, total: int, result: FetchResult) -> None:
                fetch_progress.update(1)
                typer.echo(_summarize_fetch_result(result), err=True)

            def on_status_update(message: str) -> None:
                typer.echo(message, err=True)

            result = process_isbn_file(
                input_path,
                on_fetch_start=on_fetch_start,
                on_fetch_complete=on_fetch_complete,
                on_status_update=on_status_update,
            )
    else:
        result = process_isbn_file(
            input_path,
            on_status_update=lambda message: typer.echo(message, err=True),
        )

    for resolution_result in result.resolution_results:
        typer.echo(_summarize_resolution_result(resolution_result), err=True)

    resolved_count = sum(1 for item in result.resolution_results if item.record is not None)
    unresolved_results = [item for item in result.resolution_results if item.record is None]
    unresolved_count = len(unresolved_results)
    fetched_count = sum(1 for item in result.fetch_results if item.record is not None)

    typer.echo(f"Valid ISBNs: {len(result.input_result.valid_inputs)}")
    typer.echo(f"Invalid rows: {len(result.input_result.invalid_values)}")
    if result.input_result.duplicate_count:
        typer.echo(f"Duplicates removed: {result.input_result.duplicate_count}")

    if result.input_result.invalid_values:
        typer.echo("Invalid values:")
        for invalid_value in result.input_result.invalid_values:
            typer.echo(f"- {invalid_value}")

    typer.echo(f"Fetched records: {fetched_count}")
    issue_code_counts = _count_source_issue_codes(result.fetch_results)
    if issue_code_counts:
        typer.echo("Source issue codes:")
        for issue_code, count in sorted(issue_code_counts.items()):
            typer.echo(f"- {issue_code}: {count}")

        google_rate_limited_count = issue_code_counts.get(
            "GOOGLE_BOOKS:GOOGLE_BOOKS_RATE_LIMITED",
            0,
        )
        if google_rate_limited_count:
            typer.secho(
                "Warning: Google Books rate limiting was detected. "
                "Bibliographic results may be degraded until upstream access recovers.",
                fg=typer.colors.YELLOW,
            )

    typer.echo(f"Resolved records: {resolved_count}")
    typer.echo(f"Unresolved records: {unresolved_count}")

    first_gain_counts = _count_first_material_gain_stages(result.resolution_results)
    if first_gain_counts:
        typer.echo("First material gain by stage:")
        for stage_name, count in sorted(first_gain_counts.items()):
            typer.echo(f"- {stage_name}: {count}")

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
        export_upload_records(result.resolution_results, output)
        typer.echo(f"Exported upload records to {output}")

        if handoff_output is None:
            handoff_output = _default_handoff_path(output)

    if review_output is not None:
        export_review_rows(result.resolution_results, review_output)
        typer.echo(f"Exported review records to {review_output}")

    if handoff_output is not None:
        export_handoff_results(result.resolution_results, handoff_output)
        typer.echo(f"Exported handoff results to {handoff_output}")


if __name__ == "__main__":
    app()
