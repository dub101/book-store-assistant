from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.results import ResolutionResult


def collect_resolved_records(results: list[ResolutionResult]) -> list[BookRecord]:
    return [result.record for result in results if result.record is not None]
