import json
import re

import httpx

from book_store_assistant.enrichment.base import SynopsisGenerator
from book_store_assistant.enrichment.models import DescriptiveEvidence, GeneratedSynopsis

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

GENERATED_SYNOPSIS_JSON_SCHEMA = {
    "name": "generated_synopsis",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "text": {"type": "string"},
            "language": {"type": "string"},
            "evidence_indexes": {
                "type": "array",
                "items": {"type": "integer"},
            },
        },
        "required": ["text", "language", "evidence_indexes"],
    },
    "strict": True,
}


def _build_messages(isbn: str, evidence: list[DescriptiveEvidence]) -> list[dict[str, object]]:
    evidence_lines: list[str] = []
    for index, item in enumerate(evidence):
        evidence_lines.append(
            "\n".join(
                [
                    f"Evidence #{index}",
                    f"Source: {item.source_name}",
                    f"Type: {item.evidence_type}",
                    f"Language: {item.language or 'unknown'}",
                    f"Text: {item.text}",
                ]
            )
        )

    system_prompt = (
        "You generate Spanish bookstore synopses strictly from supplied evidence. "
        "Do not invent facts. "
        "Return only valid JSON matching the required schema with keys text, language, "
        "and evidence_indexes. "
        "Use only evidence indexes that were actually provided."
    )
    user_prompt = "\n\n".join(
        [
            f"ISBN: {isbn}",
            "Generate a concise Spanish synopsis grounded only in the evidence below.",
            (
                "If the evidence is insufficient, return an empty text and an empty "
                "evidence_indexes list."
            ),
            *evidence_lines,
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

    if not text_parts:
        return None

    return "\n".join(text_parts)


def _parse_generated_synopsis(text: str) -> GeneratedSynopsis | None:
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

    synopsis_text = parsed.get("text")
    language = parsed.get("language", "es")
    evidence_indexes = parsed.get("evidence_indexes", [])

    if not isinstance(synopsis_text, str):
        return None
    if not isinstance(language, str):
        return None
    if not isinstance(evidence_indexes, list) or not all(
        isinstance(item, int) for item in evidence_indexes
    ):
        return None

    return GeneratedSynopsis(
        text=synopsis_text,
        language=language,
        evidence_indexes=evidence_indexes,
        raw_output_text=normalized_text,
    )


class OpenAISynopsisGenerator(SynopsisGenerator):
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

    def generate(
        self,
        isbn: str,
        evidence: list[DescriptiveEvidence],
    ) -> GeneratedSynopsis | None:
        try:
            response = httpx.post(
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": _build_messages(isbn, evidence),
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": GENERATED_SYNOPSIS_JSON_SCHEMA["name"],
                            "schema": GENERATED_SYNOPSIS_JSON_SCHEMA["schema"],
                            "strict": GENERATED_SYNOPSIS_JSON_SCHEMA["strict"],
                        }
                    }
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        output_text = _extract_output_text(response.json())
        if output_text is None:
            return None

        parsed = _parse_generated_synopsis(output_text)
        if parsed is not None:
            return parsed

        return GeneratedSynopsis(
            text="",
            evidence_indexes=[],
            validation_flags=["unparseable_generator_output"],
            raw_output_text=output_text,
        )
