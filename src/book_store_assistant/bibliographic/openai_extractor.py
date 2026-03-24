import json
import re

import httpx

from book_store_assistant.bibliographic.base import BibliographicEvidenceExtractor
from book_store_assistant.bibliographic.evidence import (
    WebSearchBibliographicExtraction,
    WebSearchEvidenceDocument,
)
from book_store_assistant.sources.models import SourceBookRecord

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

WEB_BIBLIOGRAPHIC_EXTRACTION_JSON_SCHEMA = {
    "name": "web_bibliographic_extraction",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "confidence": {"type": "number"},
            "title": {"type": ["string", "null"]},
            "subtitle": {"type": ["string", "null"]},
            "author": {"type": ["string", "null"]},
            "editorial": {"type": ["string", "null"]},
            "publisher": {"type": ["string", "null"]},
            "support": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "array", "items": {"type": "integer"}},
                    "subtitle": {"type": "array", "items": {"type": "integer"}},
                    "author": {"type": "array", "items": {"type": "integer"}},
                    "editorial": {"type": "array", "items": {"type": "integer"}},
                    "publisher": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["title", "subtitle", "author", "editorial", "publisher"],
            },
            "issues": {"type": "array", "items": {"type": "string"}},
            "explanation": {"type": ["string", "null"]},
        },
        "required": [
            "confidence",
            "title",
            "subtitle",
            "author",
            "editorial",
            "publisher",
            "support",
            "issues",
            "explanation",
        ],
    },
    "strict": True,
}


def _build_messages(
    source_record: SourceBookRecord,
    evidence_documents: list[WebSearchEvidenceDocument],
) -> list[dict[str, object]]:
    evidence_lines: list[str] = []
    for item in evidence_documents:
        evidence_lines.append(
            "\n".join(
                [
                    f"Document #{item.index}",
                    f"URL: {item.url}",
                    f"Domain: {item.domain}",
                    f"Page title: {item.page_title or ''}",
                    f"ISBN present on page: {'yes' if item.isbn_present else 'no'}",
                    f"Excerpt: {item.excerpt}",
                ]
            )
        )

    current_record_lines = [
        f"ISBN: {source_record.isbn}",
        f"Current title: {source_record.title or ''}",
        f"Current subtitle: {source_record.subtitle or ''}",
        f"Current author: {source_record.author or ''}",
        f"Current editorial: {source_record.editorial or ''}",
        f"Current field sources: {source_record.field_sources}",
    ]

    system_prompt = (
        "You extract bookstore upload metadata from trusted web evidence. "
        "Use only the supplied evidence documents. "
        "Never invent facts. "
        "Return null for unsupported fields. "
        "Prefer clean customer-facing values: remove catalog artifacts like '[Texto impreso]' "
        "when the evidence clearly shows the public title, and prefer editorial/imprint names "
        "without city prefixes or bracketed catalog notation when the evidence supports that "
        "cleanup. "
        "Publisher should be the broader publisher/group only when the evidence clearly supports "
        "it; "
        "otherwise publisher may equal editorial. "
        "Support indexes must reference only the supplied document numbers."
    )
    user_prompt = "\n\n".join(
        [
            "Current source record:",
            *current_record_lines,
            "",
            "Trusted web evidence:",
            *evidence_lines,
            "",
            (
                "Extract a grounded upload candidate for ISBN, title, subtitle, author, editorial, "
                "and publisher. Use the support object to cite which document indexes support "
                "each field."
            ),
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


def _clean_optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned or None


def _parse_support(value: object) -> dict[str, list[int]] | None:
    if not isinstance(value, dict):
        return None

    support: dict[str, list[int]] = {}
    for field_name in ("title", "subtitle", "author", "editorial", "publisher"):
        field_value = value.get(field_name, [])
        if not isinstance(field_value, list) or not all(
            isinstance(item, int) for item in field_value
        ):
            return None
        support[field_name] = field_value

    return support


def _parse_extraction(text: str) -> WebSearchBibliographicExtraction | None:
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

    confidence = parsed.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)):
        return None

    support = _parse_support(parsed.get("support"))
    if support is None:
        return None

    issues = parsed.get("issues", [])
    if not isinstance(issues, list):
        return None

    explanation = parsed.get("explanation")
    if explanation is not None and not isinstance(explanation, str):
        return None

    return WebSearchBibliographicExtraction(
        confidence=float(confidence),
        title=_clean_optional_text(parsed.get("title")),
        subtitle=_clean_optional_text(parsed.get("subtitle")),
        author=_clean_optional_text(parsed.get("author")),
        editorial=_clean_optional_text(parsed.get("editorial")),
        publisher=_clean_optional_text(parsed.get("publisher")),
        support=support,
        issues=[str(item).strip() for item in issues if str(item).strip()],
        explanation=(
            explanation.strip()
            if isinstance(explanation, str) and explanation.strip()
            else None
        ),
        raw_output_text=normalized_text,
    )


class OpenAIWebBibliographicExtractor(BibliographicEvidenceExtractor):
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

    def extract(
        self,
        source_record: SourceBookRecord,
        evidence_documents: list[WebSearchEvidenceDocument],
    ) -> WebSearchBibliographicExtraction | None:
        try:
            response = httpx.post(
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": _build_messages(source_record, evidence_documents),
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": WEB_BIBLIOGRAPHIC_EXTRACTION_JSON_SCHEMA["name"],
                            "schema": WEB_BIBLIOGRAPHIC_EXTRACTION_JSON_SCHEMA["schema"],
                            "strict": WEB_BIBLIOGRAPHIC_EXTRACTION_JSON_SCHEMA["strict"],
                        }
                    },
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        output_text = _extract_output_text(response.json())
        if output_text is None:
            return None

        extraction = _parse_extraction(output_text)
        if extraction is None:
            return None

        if extraction.confidence < self.min_confidence:
            return extraction.model_copy(
                update={"issues": [*extraction.issues, "extractor_low_confidence"]}
            )

        return extraction
