from book_store_assistant.resolution.books import resolve_book_record
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.results import FetchResult


def resolve_all(fetch_results: list[FetchResult]) -> list[ResolutionResult]:
    resolution_results: list[ResolutionResult] = []

    for fetch_result in fetch_results:
        if fetch_result.record is None:
            resolution_results.append(
                ResolutionResult(
                    record=None,
                    source_record=None,
                    errors=fetch_result.errors,
                )
            )
            continue

        resolution_results.append(resolve_book_record(fetch_result.record))

    return resolution_results
