import json
import re

import httpx

from book_store_assistant.resolution.base import RecordFieldSelector
from book_store_assistant.resolution.models import SelectedFieldValues
from book_store_assistant.sources.candidates import get_field_candidates
from book_store_assistant.sources.models import SourceBookRecord

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def _build_candidate_lines(record: SourceBookRecord, field_name: str) -> list[str]:
    lines: list[str] = []
    for index, candidate in enumerate(get_field_candidates(record, field_name)):
        lines.append(
            "\n".join(
                [
                    f"{field_name.title()} candidate #{index}",
                    f"Value: {candidate.value}",
                    f"Source: {candidate.source_name}",
                    f"Confidence: {candidate.confidence:.2f}",
                ]
            )
        )
    return lines


def _build_messages(record: SourceBookRecord) -> list[dict[str, object]]:
    system_prompt = (
        "You select the best bibliographic field values for a bookstore record. "
        "Choose only from the provided candidate indexes. "
        "Do not invent new values. "
        "Return only valid JSON with keys title_index, author_index, editorial_index. "
        "Use null when no candidate is trustworthy."
    )
    user_prompt = "\n\n".join(
        [
            f"ISBN: {record.isbn}",
            "Select the best candidate for each field.",
            *_build_candidate_lines(record, "title"),
            *_build_candidate_lines(record, "author"),
            *_build_candidate_lines(record, "editorial"),
        ]
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _extract_output_text(payload: dict) -> str | None:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output = payload.get("output")
    if not isinstance(output, list):
        return None

    text_parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content_items = item.get("content")
        if not isinstance(content_items, list):
            continue
        for content_item in content_items:
            if not isinstance(content_item, dict):
                continue
            text_value = content_item.get("text")
            if isinstance(text_value, str) and text_value.strip():
                text_parts.append(text_value.strip())

    return "\n".join(text_parts) if text_parts else None


def _parse_selected_indexes(text: str) -> dict[str, int | None] | None:
    normalized_text = text.strip()
    try:
        parsed = json.loads(normalized_text)
    except json.JSONDecodeError:
        match = JSON_OBJECT_PATTERN.search(normalized_text)
        if match is None:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(parsed, dict):
        return None

    selected: dict[str, int | None] = {}
    for field_name in ("title", "author", "editorial"):
        value = parsed.get(f"{field_name}_index")
        if value is None:
            selected[field_name] = None
            continue
        if not isinstance(value, int):
            return None
        selected[field_name] = value

    return selected


class OpenAIRecordFieldSelector(RecordFieldSelector):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def select_fields(self, record: SourceBookRecord) -> SelectedFieldValues | None:
        try:
            response = httpx.post(
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": _build_messages(record),
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        output_text = _extract_output_text(response.json())
        if output_text is None:
            return None

        selected_indexes = _parse_selected_indexes(output_text)
        if selected_indexes is None:
            return None

        values: dict[str, str | None] = {}
        supporting_indexes: dict[str, int] = {}
        for field_name in ("title", "author", "editorial"):
            candidates = get_field_candidates(record, field_name)
            candidate_index = selected_indexes.get(field_name)
            if candidate_index is None or candidate_index < 0 or candidate_index >= len(candidates):
                values[field_name] = None
                continue
            values[field_name] = candidates[candidate_index].value
            supporting_indexes[field_name] = candidate_index

        return SelectedFieldValues(
            title=values["title"],
            author=values["author"],
            editorial=values["editorial"],
            supporting_indexes=supporting_indexes,
        )
