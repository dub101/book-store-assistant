from pathlib import Path

from book_store_assistant.export.excel import export_books
from book_store_assistant.pipeline.output import collect_resolved_records
from book_store_assistant.resolution.results import ResolutionResult


def export_resolved_records(results: list[ResolutionResult], output_path: Path) -> None:
    records = collect_resolved_records(results)
    export_books(records, output_path)
