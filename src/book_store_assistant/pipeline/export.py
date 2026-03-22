from pathlib import Path

from book_store_assistant.bibliographic.export import export_upload_records
from book_store_assistant.resolution.results import ResolutionResult


def export_resolved_records(results: list[ResolutionResult], output_path: Path) -> None:
    export_upload_records(results, output_path)
