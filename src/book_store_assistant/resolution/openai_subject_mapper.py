import json
import re

import httpx

from book_store_assistant.resolution.base import SubjectMapper
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.subjects import SubjectEntry

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def _build_messages(
    record: SourceBookRecord,
    allowed_subject_entries: list[SubjectEntry],
) -> list[dict[str, object]]:
    subject_lines = [
        f"- {entry.description}" for entry in allowed_subject_entries
    ]
    record_lines = [
        f"ISBN: {record.isbn}",
        f"Title: {record.title or ''}",
        f"Subtitle: {record.subtitle or ''}",
        f"Author: {record.author or ''}",
        f"Editorial: {record.editorial or ''}",
        f"Subject: {record.subject or ''}",
        f"Categories: {', '.join(record.categories)}",
        f"Synopsis: {record.synopsis or ''}",
    ]
    system_prompt = (
        "You map bookstore records to an allowed internal subject catalog. "
        "Choose only one exact subject from the supplied catalog descriptions. "
        "Do not invent subjects. "
        "If the evidence is insufficient, return an empty subject and confidence 0. "
        "Return only valid JSON with keys subject and confidence."
    )
    user_prompt = "\n".join(
        [
            "Allowed catalog subjects:",
            *subject_lines,
            "",
            "Record:",
            *record_lines,
        ]
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _parse_subject_response(text: str) -> tuple[str | None, float]:
    normalized_text = text.strip()
    try:
        parsed = json.loads(normalized_text)
    except json.JSONDecodeError:
        match = JSON_OBJECT_PATTERN.search(normalized_text)
        if match is None:
            return None, 0.0
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None, 0.0

    if not isinstance(parsed, dict):
        return None, 0.0

    subject = parsed.get("subject")
    confidence = parsed.get("confidence", 0.0)

    if not isinstance(subject, str):
        subject = None
    if not isinstance(confidence, (int, float)):
        confidence = 0.0

    cleaned_subject = subject.strip() if subject else ""
    return (cleaned_subject or None), float(confidence)


class OpenAISubjectMapper(SubjectMapper):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        min_confidence: float,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.min_confidence = min_confidence

    def map_subject(
        self,
        record: SourceBookRecord,
        allowed_subject_entries: list[SubjectEntry],
    ) -> str | None:
        response = httpx.post(
            f"{self.base_url}/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": _build_messages(record, allowed_subject_entries),
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        output_text = payload.get("output_text")
        if not isinstance(output_text, str) or not output_text.strip():
            return None

        subject, confidence = _parse_subject_response(output_text)
        if subject is None or confidence < self.min_confidence:
            return None

        allowed_subjects = {
            entry.description.strip().casefold(): entry.description
            for entry in allowed_subject_entries
        }
        return allowed_subjects.get(subject.casefold())
