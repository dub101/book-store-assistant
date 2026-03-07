from pathlib import Path

from book_store_assistant.models import BookRecord


def export_books(records: list[BookRecord], output_path: Path) -> None:
    """Export book records to an Excel file."""
    raise NotImplementedError("Excel export is not implemented yet.")
