from pathlib import Path

from book_store_assistant.bibliographic.export import export_review_rows
from book_store_assistant.resolution.results import ResolutionResult


def export_unresolved_results(results: list[ResolutionResult], output_path: Path) -> None:
    export_review_rows(results, output_path)
