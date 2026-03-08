from pathlib import Path

from book_store_assistant.export.review import export_review_rows
from book_store_assistant.pipeline.review import collect_unresolved_results
from book_store_assistant.resolution.results import ResolutionResult


def export_unresolved_results(results: list[ResolutionResult], output_path: Path) -> None:
    unresolved = collect_unresolved_results(results)
    export_review_rows(unresolved, output_path)
