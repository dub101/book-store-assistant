"""LLM-powered bibliographic enrichment using OpenAI Responses API with web search."""
import csv
import json
import re
import time
import unicodedata
from collections.abc import Callable
from pathlib import Path

import httpx

from book_store_assistant.sources.diagnostics import changed_record_fields, with_diagnostic
from book_store_assistant.sources.merge import merge_source_records
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult

LLMEnrichmentStatusCallback = Callable[[str], None]

LLM_ENRICHMENT_SOURCE_NAME = "llm_web_search"

_SUBJECTS_PATH = Path(__file__).parent.parent.parent.parent / "data" / "reference" / "subjects.tsv"

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

ENRICHMENT_JSON_SCHEMA = {
    "name": "bibliographic_enrichment",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "title": {"type": ["string", "null"]},
            "subtitle": {"type": ["string", "null"]},
            "author": {"type": ["string", "null"]},
            "editorial": {"type": ["string", "null"]},
            "synopsis": {"type": ["string", "null"]},
            "subject_name": {"type": ["string", "null"]},
            "subject_code": {"type": ["string", "null"]},
            "cover_url": {"type": ["string", "null"]},
        },
        "required": [
            "title", "subtitle", "author", "editorial",
            "synopsis", "subject_name", "subject_code", "cover_url",
        ],
        "additionalProperties": False,
    },
}


def _load_subject_catalog(path: Path | None = None) -> list[dict[str, str]]:
    tsv_path = path or _SUBJECTS_PATH
    if not tsv_path.exists():
        return []
    rows: list[dict[str, str]] = []
    with tsv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append(dict(row))
    return rows


def _format_catalog_for_prompt(catalog: list[dict[str, str]]) -> str:
    lines = ["Code | Subject"]
    for row in catalog:
        code = row.get("Subject", "").strip()
        description = row.get("Description", "").strip()
        if code and description and len(code) >= 4:
            lines.append(f"{code} | {description}")
    return "\n".join(lines)


def _build_enrichment_prompt(
    isbn: str,
    partial: SourceBookRecord | None,
    catalog_text: str,
) -> list[dict[str, object]]:
    known_lines = [f"ISBN: {isbn}"]
    if partial is not None:
        if partial.title:
            known_lines.append(f"Title (partial): {partial.title}")
        if partial.subtitle:
            known_lines.append(f"Subtitle (partial): {partial.subtitle}")
        if partial.author:
            known_lines.append(f"Author (partial): {partial.author}")
        if partial.editorial:
            known_lines.append(f"Editorial (partial): {partial.editorial}")
        if partial.language:
            known_lines.append(f"Language: {partial.language}")
        if partial.categories:
            known_lines.append(f"Categories from source: {', '.join(partial.categories)}")

    known_block = "\n".join(known_lines)

    user_message = f"""Search the web to find complete bibliographic information for this book.

Known data:
{known_block}

Return the following fields:
- title: the book's title
- subtitle: subtitle if any, otherwise null
- author: author name(s) as they appear on the cover
- editorial: the specific imprint or editorial label (e.g. "Debolsillo", "Alfaguara", "Planeta") — not the parent group
- synopsis: a book synopsis or description IN SPANISH. Search for a Spanish-language description. If only a non-Spanish description exists, translate it to Spanish. Return null only if no description can be found anywhere.
- subject_name: pick the single best matching subject from this catalog. You MUST use the Description value (second column) exactly as written — copy it verbatim. Pick the most specific category that fits the book. For classic literature (pre-1950), use CLASICOS. For Latin American authors, use LITERATURA LATINOAMERICANA. For crime/mystery/thriller, use THRILLER O NOVELA NEGRA.

{catalog_text}

- subject_code: the Code value (first column) for the chosen subject. Must be a 4-digit number from the catalog above.
- cover_url: a direct URL to the book cover image, or null if not found.

Return null for any field you cannot determine with confidence. Do not invent data."""

    return [{"role": "user", "content": user_message}]


def _parse_enrichment_response(response_json: dict) -> dict | None:
    output = response_json.get("output", [])
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            content = item.get("content", [])
            for block in content:
                if isinstance(block, dict) and block.get("type") == "output_text":
                    text = block.get("text", "")
                    match = JSON_OBJECT_PATTERN.search(text)
                    if match:
                        try:
                            return json.loads(match.group())
                        except json.JSONDecodeError:
                            return None
    return None


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def _match_catalog_subject(
    subject_name: str | None,
    subject_code: str | None,
    catalog: list[dict[str, str]],
) -> tuple[str | None, str | None]:
    if not catalog:
        return subject_name, subject_code

    if subject_code:
        for row in catalog:
            if row.get("Subject", "").strip() == subject_code.strip():
                return row.get("Description", "").strip() or subject_name, subject_code
    if subject_name:
        name_norm = _strip_accents(subject_name.strip().lower())
        for row in catalog:
            desc = row.get("Description", "").strip()
            if _strip_accents(desc.lower()) == name_norm:
                return desc, row.get("Subject", "").strip()
        for row in catalog:
            desc = row.get("Description", "").strip()
            desc_norm = _strip_accents(desc.lower())
            if name_norm in desc_norm or desc_norm in name_norm:
                return desc, row.get("Subject", "").strip()
    return subject_name, subject_code


def _build_enriched_record(
    isbn: str,
    data: dict,
    existing: SourceBookRecord | None,
    catalog: list[dict[str, str]] | None = None,
) -> SourceBookRecord | None:
    title = (data.get("title") or "").strip() or None
    subtitle = (data.get("subtitle") or "").strip() or None
    author = (data.get("author") or "").strip() or None
    editorial = (data.get("editorial") or "").strip() or None
    synopsis = (data.get("synopsis") or "").strip() or None
    subject = (data.get("subject_name") or "").strip() or None
    subject_code = (data.get("subject_code") or "").strip() or None
    cover_url_raw = (data.get("cover_url") or "").strip() or None

    if catalog:
        subject, subject_code = _match_catalog_subject(subject, subject_code, catalog)

    if not any((title, author, editorial, synopsis, subject)):
        return None

    field_sources: dict[str, str] = {}
    field_confidence: dict[str, float] = {}

    for field_name, value in [
        ("title", title),
        ("subtitle", subtitle),
        ("author", author),
        ("editorial", editorial),
        ("synopsis", synopsis),
        ("subject", subject),
        ("subject_code", subject_code),
    ]:
        if value:
            field_sources[field_name] = LLM_ENRICHMENT_SOURCE_NAME
            field_confidence[field_name] = 0.85

    if cover_url_raw:
        field_sources["cover_url"] = LLM_ENRICHMENT_SOURCE_NAME
        field_confidence["cover_url"] = 0.8

    from pydantic import HttpUrl, ValidationError

    try:
        cover_url: HttpUrl | None = HttpUrl(cover_url_raw) if cover_url_raw else None
    except ValidationError:
        cover_url = None

    language = existing.language if existing else None
    language = existing.language if existing else None
    categories = existing.categories if existing else []

    return SourceBookRecord(
        source_name=LLM_ENRICHMENT_SOURCE_NAME,
        isbn=isbn,
        title=title,
        subtitle=subtitle,
        author=author,
        editorial=editorial,
        synopsis=synopsis,
        subject=subject,
        subject_code=subject_code,
        cover_url=cover_url,
        language=language,
        categories=categories,
        field_sources=field_sources,
        field_confidence=field_confidence,
    )


def _needs_enrichment(result: FetchResult) -> bool:
    record = result.record
    if record is None:
        return True
    return not (
        bool((record.title or "").strip())
        and bool((record.author or "").strip())
        and bool((record.editorial or "").strip())
    )


class LLMWebEnricher:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        catalog_path: Path | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.catalog = _load_subject_catalog(catalog_path)
        self.catalog_text = _format_catalog_for_prompt(self.catalog)

    def _call_api(self, messages: list[dict[str, object]]) -> dict | None:
        try:
            response = httpx.post(
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "tools": [{"type": "web_search_preview"}],
                    "input": messages,
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": ENRICHMENT_JSON_SCHEMA["name"],
                            "schema": ENRICHMENT_JSON_SCHEMA["schema"],
                            "strict": ENRICHMENT_JSON_SCHEMA["strict"],
                        }
                    },
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        return _parse_enrichment_response(response.json())

    def enrich(self, isbn: str, partial: SourceBookRecord | None) -> SourceBookRecord | None:
        messages = _build_enrichment_prompt(isbn, partial, self.catalog_text)
        data = self._call_api(messages)
        if data is None:
            time.sleep(self.timeout_seconds / 10)
            data = self._call_api(messages)
        if data is None:
            return None

        return _build_enriched_record(isbn, data, partial, catalog=self.catalog)


def augment_fetch_results_with_llm_enrichment(
    fetch_results: list[FetchResult],
    enricher: LLMWebEnricher,
    on_status_update: LLMEnrichmentStatusCallback | None = None,
) -> list[FetchResult]:
    result_by_isbn: dict[str, FetchResult] = {}
    unique_results: list[FetchResult] = []
    for r in fetch_results:
        if r.isbn not in result_by_isbn:
            result_by_isbn[r.isbn] = r
            unique_results.append(r)

    targeted = [r for r in unique_results if _needs_enrichment(r)]
    if not targeted:
        return fetch_results

    if on_status_update is not None:
        on_status_update(
            f"Stage: LLM web enrichment for {len(targeted)} records"
        )

    targeted_index = 0
    for fetch_result in unique_results:
        if not _needs_enrichment(fetch_result):
            continue

        targeted_index += 1
        if on_status_update is not None:
            on_status_update(
                f"LLM enrichment {targeted_index}/{len(targeted)}: {fetch_result.isbn}"
            )

        enriched_record = enricher.enrich(fetch_result.isbn, fetch_result.record)
        if enriched_record is None:
            result_by_isbn[fetch_result.isbn] = with_diagnostic(
                fetch_result,
                "llm_enrichment",
                "enrichment_failed",
            )
            continue

        if fetch_result.record is not None:
            merged = merge_source_records([fetch_result.record, enriched_record])
        else:
            merged = enriched_record

        changed_fields = changed_record_fields(fetch_result.record, merged)
        updated = with_diagnostic(
            fetch_result,
            "llm_enrichment",
            "record_updated",
            changed_fields=changed_fields,
        ).model_copy(update={"record": merged})

        result_by_isbn[fetch_result.isbn] = updated

    return [result_by_isbn[r.isbn] for r in fetch_results]
