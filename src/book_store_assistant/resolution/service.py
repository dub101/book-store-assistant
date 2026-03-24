from book_store_assistant.bibliographic.resolution import resolve_bibliographic_record
from book_store_assistant.resolution.base import RecordQualityValidator
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.diagnostics import build_path_summary
from book_store_assistant.sources.issues import format_issue_detail
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


def resolve_all(
    fetch_results: list[FetchResult],
    validator: RecordQualityValidator | None = None,
) -> list[ResolutionResult]:
    resolution_results: list[ResolutionResult] = []

    for fetch_result in fetch_results:
        if fetch_result.record is None:
            fetch_error_record = SourceBookRecord(
                source_name="fetch_error",
                isbn=fetch_result.isbn,
            )
            resolution_results.append(
                ResolutionResult(
                    record=None,
                    source_record=fetch_error_record,
                    errors=fetch_result.errors,
                    reason_codes=[FETCH_ERROR_CODE] if fetch_result.errors else [],
                    review_details=[
                        *[
                            format_issue_detail(issue_code)
                            for issue_code in fetch_result.issue_codes
                        ],
                        *fetch_result.errors,
                    ],
                    diagnostics=fetch_result.diagnostics,
                    path_summary=build_path_summary(fetch_result.diagnostics, fetch_error_record),
                )
            )
            continue

        resolved_result = resolve_bibliographic_record(
            fetch_result.record,
            publisher_identity=fetch_result.publisher_identity,
            validator=validator,
        )

        if resolved_result.record is None and fetch_result.errors:
            merged_reason_codes = _merge_unique(
                [FETCH_ERROR_CODE],
                resolved_result.reason_codes,
            )
            merged_review_details = _merge_unique(
                [format_issue_detail(issue_code) for issue_code in fetch_result.issue_codes],
                fetch_result.errors,
                resolved_result.review_details,
            )
            resolution_results.append(
                ResolutionResult(
                    record=None,
                    candidate_record=resolved_result.candidate_record,
                    source_record=resolved_result.source_record,
                    publisher_identity=resolved_result.publisher_identity,
                    validation_assessment=resolved_result.validation_assessment,
                    errors=_merge_unique(fetch_result.errors, resolved_result.errors),
                    reason_codes=merged_reason_codes,
                    review_details=merged_review_details,
                    diagnostics=fetch_result.diagnostics,
                    path_summary=build_path_summary(
                        fetch_result.diagnostics,
                        resolved_result.source_record,
                    ),
                )
            )
            continue

        resolution_results.append(
            resolved_result.model_copy(
                update={
                    "diagnostics": fetch_result.diagnostics,
                    "path_summary": build_path_summary(
                        fetch_result.diagnostics,
                        resolved_result.source_record,
                    ),
                }
            )
        )

    return resolution_results
