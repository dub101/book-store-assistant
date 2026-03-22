from collections.abc import Iterable
from typing import Any

from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult

TRACKED_FIELDS = ("title", "subtitle", "author", "editorial", "source_url")


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


def diagnostic_event(stage: str, action: str, **details: Any) -> dict[str, Any]:
    event = {"stage": stage, "action": action}
    for key, value in details.items():
        if value is None:
            continue
        event[key] = value
    return event


def with_diagnostic(
    fetch_result: FetchResult,
    stage: str,
    action: str,
    **details: Any,
) -> FetchResult:
    return fetch_result.model_copy(
        update={
            "diagnostics": [
                *fetch_result.diagnostics,
                diagnostic_event(stage, action, **details),
            ]
        }
    )
