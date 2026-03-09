from book_store_assistant.resolution.books import resolve_book_record
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


def _merge_errors(*error_lists: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for errors in error_lists:
        for error in errors:
            if error in seen:
                continue
            seen.add(error)
            merged.append(error)

    return merged


def resolve_all(fetch_results: list[FetchResult]) -> list[ResolutionResult]:
    resolution_results: list[ResolutionResult] = []

    for fetch_result in fetch_results:
        if fetch_result.record is None:
            resolution_results.append(
                ResolutionResult(
                    record=None,
                    source_record=SourceBookRecord(
                        source_name="fetch_error",
                        isbn=fetch_result.isbn,
                    ),
                    errors=fetch_result.errors,
                )
            )
            continue

        resolved_result = resolve_book_record(fetch_result.record)

        if resolved_result.record is None and fetch_result.errors:
            resolution_results.append(
                ResolutionResult(
                    record=None,
                    source_record=resolved_result.source_record,
                    errors=_merge_errors(fetch_result.errors, resolved_result.errors),
                )
            )
            continue

        resolution_results.append(resolved_result)

    return resolution_results
