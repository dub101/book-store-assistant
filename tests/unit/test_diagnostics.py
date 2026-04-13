from book_store_assistant.sources.diagnostics import (
    build_path_summary,
    changed_record_fields,
    with_diagnostic,
)
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


def _make_record(**overrides: object) -> SourceBookRecord:
    defaults = {"source_name": "test", "isbn": "9780306406157"}
    return SourceBookRecord(**{**defaults, **overrides})


# -- changed_record_fields --


def test_changed_record_fields_detects_changes_between_two_records() -> None:
    previous = _make_record(title="Old Title", author="Author A")
    current = _make_record(title="New Title", author="Author A")

    result = changed_record_fields(previous, current)

    assert "title" in result
    assert "author" not in result


def test_changed_record_fields_no_changes_returns_empty_list() -> None:
    record = _make_record(title="Same", author="Same Author")

    result = changed_record_fields(record, record)

    assert result == []


def test_changed_record_fields_previous_none_reports_all_fields_changed() -> None:
    current = _make_record(
        title="Title",
        subtitle="Sub",
        author="Author",
        editorial="Editorial",
        source_url="https://example.com",
    )

    result = changed_record_fields(None, current)

    assert "title" in result
    assert "subtitle" in result
    assert "author" in result
    assert "editorial" in result
    assert "source_url" in result


def test_changed_record_fields_both_none_no_changes() -> None:
    result = changed_record_fields(None, None)

    assert result == []


# -- with_diagnostic --


def test_with_diagnostic_adds_event_to_fetch_result() -> None:
    fetch_result = FetchResult(isbn="9780306406157", record=None, errors=[])

    updated = with_diagnostic(
        fetch_result, stage="google_books", action="started", url="http://example.com"
    )

    assert len(updated.diagnostics) == 1
    event = updated.diagnostics[0]
    assert event["stage"] == "google_books"
    assert event["action"] == "started"
    assert event["url"] == "http://example.com"


def test_with_diagnostic_appends_to_existing_diagnostics() -> None:
    fetch_result = FetchResult(
        isbn="9780306406157",
        record=None,
        errors=[],
        diagnostics=[{"stage": "bne", "action": "started"}],
    )

    updated = with_diagnostic(fetch_result, stage="google_books", action="completed")

    assert len(updated.diagnostics) == 2
    assert updated.diagnostics[0]["stage"] == "bne"
    assert updated.diagnostics[1]["stage"] == "google_books"


def test_with_diagnostic_omits_none_details() -> None:
    fetch_result = FetchResult(isbn="9780306406157", record=None, errors=[])

    updated = with_diagnostic(
        fetch_result, stage="bne", action="completed", extra=None
    )

    event = updated.diagnostics[0]
    assert "extra" not in event


# -- build_path_summary --


def test_build_path_summary_builds_from_diagnostics_list() -> None:
    diagnostics = [
        {"stage": "bne", "action": "started"},
        {"stage": "bne", "action": "completed", "issue_codes": ["BNE_NO_MATCH"]},
        {"stage": "google_books", "action": "started"},
        {"stage": "google_books", "action": "completed", "changed_fields": ["title"]},
    ]
    record = _make_record(field_sources={"title": "google_books", "author": "bne"})

    summary = build_path_summary(diagnostics, record)

    assert summary["stages_seen"] == ["bne", "google_books"]
    assert "bne" in summary["stage_details"]
    assert summary["stage_details"]["bne"]["issue_codes"] == ["BNE_NO_MATCH"]
    assert summary["stage_details"]["google_books"]["changed_fields"] == ["title"]
    assert summary["final_source_name"] == "test"
    assert summary["final_field_sources"] == {"title": "google_books", "author": "bne"}


def test_build_path_summary_empty_diagnostics_returns_minimal_summary() -> None:
    summary = build_path_summary([], None)

    assert summary["stages_seen"] == []
    assert summary["stage_details"] == {}
    assert "first_material_gain_stage" not in summary
    assert "final_source_name" not in summary


def test_build_path_summary_handles_first_material_gain_tracking() -> None:
    diagnostics = [
        {"stage": "bne", "action": "record_updated", "changed_fields": ["title"]},
        {
            "stage": "google_books",
            "action": "record_updated",
            "changed_fields": ["author", "editorial"],
            "first_material_gain": True,
        },
        {
            "stage": "open_library",
            "action": "record_updated",
            "changed_fields": ["synopsis"],
            "first_material_gain": True,
        },
    ]

    summary = build_path_summary(diagnostics, None)

    assert summary["first_material_gain_stage"] == "google_books"
    assert summary["first_material_gain_fields"] == ["author", "editorial"]


def test_build_path_summary_skips_diagnostics_without_stage() -> None:
    diagnostics = [
        {"action": "started"},
        {"stage": "", "action": "started"},
        {"stage": "bne", "action": "started"},
    ]

    summary = build_path_summary(diagnostics, None)

    assert summary["stages_seen"] == ["bne"]


def test_build_path_summary_includes_source_record_field_sources() -> None:
    record = _make_record(
        field_sources={
            "title": "google_books",
            "editorial": "bne",
            "untracked_field": "other",
        }
    )

    summary = build_path_summary([], record)

    assert summary["final_source_name"] == "test"
    assert "title" in summary["final_field_sources"]
    assert "editorial" in summary["final_field_sources"]
    assert "untracked_field" not in summary["final_field_sources"]
