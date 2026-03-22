import json
import re

import httpx

from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.base import RecordQualityValidator
from book_store_assistant.resolution.models import RecordValidationAssessment
from book_store_assistant.sources.models import SourceBookRecord

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def _build_messages(
    source_record: SourceBookRecord,
    candidate_record: BibliographicRecord,
) -> list[dict[str, object]]:
    source_lines = [
        f"ISBN: {source_record.isbn}",
        f"Source name: {source_record.source_name}",
        f"Source title: {source_record.title or ''}",
        f"Source subtitle: {source_record.subtitle or ''}",
        f"Source author: {source_record.author or ''}",
        f"Source editorial: {source_record.editorial or ''}",
        f"Source language: {source_record.language or ''}",
        f"Source categories: {', '.join(source_record.categories)}",
        f"Field sources: {source_record.field_sources}",
    ]
    candidate_lines = [
        f"ISBN: {candidate_record.isbn}",
        f"Title: {candidate_record.title}",
        f"Subtitle: {candidate_record.subtitle or ''}",
        f"Author: {candidate_record.author}",
        f"Editorial: {candidate_record.editorial}",
        f"Publisher: {candidate_record.publisher}",
    ]
    system_prompt = (
        "You validate bookstore upload rows for bibliographic correctness. "
        "Use the source evidence only. "
        "Accept the row unless there is a clear reason that title, subtitle, author, editorial, "
        "or publisher is unsupported, corrupted, hallucinated, mismatched to the ISBN, "
        "or obviously scraped site boilerplate. "
        "It is acceptable for editorial and publisher to be the same value when the evidence "
        "supports only one trusted publishing name. "
        "Return only valid JSON with keys accepted, confidence, issues, and explanation."
    )
    user_prompt = "\n".join(
        [
            "Candidate upload row:",
            *candidate_lines,
            "",
            "Source evidence:",
            *source_lines,
            "",
            "Accept the row unless there is a clear, concrete reason it is unsafe for upload.",
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


def _parse_validation_response(text: str) -> RecordValidationAssessment | None:
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

    accepted = parsed.get("accepted")
    confidence = parsed.get("confidence", 0.0)
    issues = parsed.get("issues", [])
    explanation = parsed.get("explanation")

    if not isinstance(accepted, bool):
        return None
    if not isinstance(confidence, (int, float)):
        confidence = 0.0
    if not isinstance(issues, list):
        issues = []
    cleaned_issues = [str(item).strip() for item in issues if str(item).strip()]
    if not isinstance(explanation, str):
        explanation = None

    return RecordValidationAssessment(
        accepted=accepted,
        confidence=float(confidence),
        issues=cleaned_issues,
        explanation=explanation.strip() if explanation else None,
    )


class OpenAIBibliographicValidator(RecordQualityValidator):
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

    def validate(
        self,
        source_record: SourceBookRecord,
        candidate_record: BookRecord | BibliographicRecord,
    ) -> RecordValidationAssessment | None:
        if not isinstance(candidate_record, BibliographicRecord):
            return None

        try:
            response = httpx.post(
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": _build_messages(source_record, candidate_record),
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        payload = response.json()
        output_text = _extract_output_text(payload)
        if not isinstance(output_text, str) or not output_text.strip():
            return None

        assessment = _parse_validation_response(output_text)
        if assessment is None:
            return None

        if assessment.accepted:
            if assessment.confidence < self.min_confidence:
                return assessment.model_copy(
                    update={"issues": [*assessment.issues, "validator_low_confidence"]}
                )
            return assessment

        if assessment.confidence < self.min_confidence:
            return RecordValidationAssessment(
                accepted=False,
                confidence=assessment.confidence,
                issues=[*assessment.issues, "validator_low_confidence"],
                explanation=assessment.explanation,
            )

        return assessment
