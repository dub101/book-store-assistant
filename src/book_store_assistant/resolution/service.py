from book_store_assistant.resolution.books import resolve_book_record
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


FETCH_ERROR_CODE = "FETCH_ERROR"


def _merge_unique(*values: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for items in values:
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)

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
                    reason_codes=[FETCH_ERROR_CODE] if fetch_result.errors else [],
                    review_details=fetch_result.errors,
                )
            )
            continue

        resolved_result = resolve_book_record(fetch_result.record)

        if resolved_result.record is None and fetch_result.errors:
            merged_reason_codes = _merge_unique(
                [FETCH_ERROR_CODE],
                resolved_result.reason_codes,
            )
            merged_review_details = _merge_unique(
                fetch_result.errors,
                resolved_result.review_details,
            )
            resolution_results.append(
                ResolutionResult(
                    record=None,
                    source_record=resolved_result.source_record,
                    errors=_merge_unique(fetch_result.errors, resolved_result.errors),
                    reason_codes=merged_reason_codes,
                    review_details=merged_review_details,
                )
            )
            continue

        resolution_results.append(resolved_result)

    return resolution_results
