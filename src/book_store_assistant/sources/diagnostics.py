from collections.abc import Iterable
from typing import Any

from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult

TRACKED_FIELDS = ("title", "subtitle", "author", "editorial", "source_url")
SUMMARY_DETAIL_KEYS = (
    "issue_codes",
    "changed_fields",
    "fetched_domains",
    "documents_found",
    "document_domains",
    "search_queries",
    "search_domains",
    "search_attempts",
    "fetch_attempts",
    "retailer_match",
    "retailer_source",
    "retailer_editorial",
    "retailer_source_url",
    "agapea_direct_success",
    "publisher_match",
    "publisher_source",
    "publisher_editorial",
    "publisher_source_url",
    "publisher_profiles",
    "candidate_urls",
    "web_search_match",
    "extraction_used",
    "extraction_confidence",
    "extraction_issues",
    "extracted_fields",
    "forced",
)


def changed_record_fields(
    previous: SourceBookRecord | None,
    current: SourceBookRecord | None,
    fields: Iterable[str] = TRACKED_FIELDS,
) -> list[str]:
    changed: list[str] = []
    for field_name in fields:
        previous_value = getattr(previous, field_name, None) if previous is not None else None
        current_value = getattr(current, field_name, None) if current is not None else None
        if previous_value != current_value:
            changed.append(field_name)
    return changed


def with_diagnostic(
    fetch_result: FetchResult,
    stage: str,
    action: str,
    **details: Any,
) -> FetchResult:
    event = {"stage": stage, "action": action}
    for key, value in details.items():
        if value is not None:
            event[key] = value

    return fetch_result.model_copy(
        update={
            "diagnostics": [
                *fetch_result.diagnostics,
                event,
            ]
        }
    )


def build_path_summary(
    diagnostics: list[dict[str, Any]],
    source_record: SourceBookRecord | None,
) -> dict[str, Any]:
    stages_seen: list[str] = []
    stage_details: dict[str, dict[str, Any]] = {}
    first_material_gain_stage: str | None = None
    first_material_gain_fields: list[str] = []

    for diagnostic in diagnostics:
        stage = diagnostic.get("stage")
        if not isinstance(stage, str) or not stage:
            continue

        if stage not in stages_seen:
            stages_seen.append(stage)

        detail = stage_details.setdefault(stage, {})
        action = diagnostic.get("action")
        if action == "completed":
            for key in SUMMARY_DETAIL_KEYS:
                if key in diagnostic:
                    detail[key] = diagnostic[key]
        elif action == "record_updated":
            changed_fields = diagnostic.get("changed_fields")
            if isinstance(changed_fields, list):
                detail["changed_fields"] = changed_fields
            if first_material_gain_stage is None and diagnostic.get("first_material_gain"):
                first_material_gain_stage = stage
                first_material_gain_fields = (
                    changed_fields if isinstance(changed_fields, list) else []
                )

    summary: dict[str, Any] = {
        "stages_seen": stages_seen,
        "stage_details": stage_details,
    }
    if first_material_gain_stage is not None:
        summary["first_material_gain_stage"] = first_material_gain_stage
        summary["first_material_gain_fields"] = first_material_gain_fields

    if source_record is not None:
        final_field_sources = {
            field_name: source_record.field_sources[field_name]
            for field_name in TRACKED_FIELDS
            if field_name in source_record.field_sources
        }
        summary["final_source_name"] = source_record.source_name
        summary["final_field_sources"] = final_field_sources

    return summary
