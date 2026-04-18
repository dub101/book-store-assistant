from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.cli import (
    _count_first_material_gain_stages,
    _count_source_issue_codes,
    _summarize_fetch_result,
    _summarize_resolution_result,
)
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


def _source_record(isbn: str = "9780306406157") -> SourceBookRecord:
    return SourceBookRecord(source_name="google_books", isbn=isbn)


def test_summarize_fetch_result_reports_metadata_with_source_errors() -> None:
    result = FetchResult(
        isbn="9780306406157",
        record=_source_record(),
        errors=["stale cache"],
    )
    assert _summarize_fetch_result(result) == "9780306406157: metadata fetched with source errors"


def test_summarize_fetch_result_reports_metadata_when_errors_absent() -> None:
    result = FetchResult(isbn="9780306406157", record=_source_record(), errors=[])
    assert _summarize_fetch_result(result) == "9780306406157: metadata fetched"


def test_summarize_fetch_result_reports_fetch_failure_when_errors_and_no_record() -> None:
    result = FetchResult(isbn="9780306406157", record=None, errors=["timeout"])
    assert _summarize_fetch_result(result) == "9780306406157: fetch failed"


def test_summarize_fetch_result_reports_no_metadata_when_nothing_found() -> None:
    result = FetchResult(isbn="9780306406157", record=None, errors=[])
    assert _summarize_fetch_result(result) == "9780306406157: no metadata found"


def test_summarize_resolution_result_reports_resolved_record() -> None:
    result = ResolutionResult(
        record=BibliographicRecord(
            isbn="9780306406157",
            title="T",
            author="A",
            editorial="E",
        ),
        candidate_record=None,
        source_record=_source_record(),
        errors=[],
        reason_codes=[],
        review_details=[],
    )
    assert _summarize_resolution_result(result) == "9780306406157: resolved"


def test_summarize_resolution_result_reports_review_with_reason_codes() -> None:
    result = ResolutionResult(
        record=None,
        candidate_record=None,
        source_record=_source_record(),
        errors=[],
        reason_codes=["VALIDATION_REJECTED", "LOW_CONFIDENCE"],
        review_details=[],
    )
    assert (
        _summarize_resolution_result(result)
        == "9780306406157: review (VALIDATION_REJECTED, LOW_CONFIDENCE)"
    )


def test_summarize_resolution_result_reports_review_without_reason_codes() -> None:
    result = ResolutionResult(
        record=None,
        candidate_record=None,
        source_record=_source_record(),
        errors=[],
        reason_codes=[],
        review_details=[],
    )
    assert _summarize_resolution_result(result) == "9780306406157: review"


def test_summarize_resolution_result_handles_missing_source_record() -> None:
    result = ResolutionResult(
        record=None,
        candidate_record=None,
        source_record=None,
        errors=[],
        reason_codes=["NO_SOURCE"],
        review_details=[],
    )
    assert _summarize_resolution_result(result) == "unknown-isbn: review (NO_SOURCE)"


def test_count_source_issue_codes_aggregates_across_results() -> None:
    results = [
        FetchResult(isbn="a", record=None, errors=[], issue_codes=["GB:RATE", "GB:RATE"]),
        FetchResult(isbn="b", record=None, errors=[], issue_codes=["GB:RATE", "OL:404"]),
    ]
    counter = _count_source_issue_codes(results)
    assert counter["GB:RATE"] == 3
    assert counter["OL:404"] == 1


def test_count_first_material_gain_stages_aggregates_string_entries_only() -> None:
    result_with_stage = ResolutionResult(
        record=None,
        candidate_record=None,
        source_record=_source_record(),
        errors=[],
        reason_codes=[],
        review_details=[],
        path_summary={"first_material_gain_stage": "isbndb"},
    )
    result_without_stage = ResolutionResult(
        record=None,
        candidate_record=None,
        source_record=_source_record("9780306406158"),
        errors=[],
        reason_codes=[],
        review_details=[],
        path_summary={"first_material_gain_stage": None},
    )
    counter = _count_first_material_gain_stages(
        [result_with_stage, result_with_stage, result_without_stage]
    )
    assert counter["isbndb"] == 2
    assert None not in counter
