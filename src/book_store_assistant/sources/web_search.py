import json
import re
import time
from collections.abc import Callable
from itertools import islice
from urllib.parse import urlparse

import httpx

from book_store_assistant.bibliographic.base import BibliographicEvidenceExtractor
from book_store_assistant.bibliographic.evidence import (
    WebSearchBibliographicExtraction,
    WebSearchEvidenceDocument,
)
from book_store_assistant.sources.issues import no_match_issue_code
from book_store_assistant.sources.merge import merge_source_records
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.publisher_pages import (
    SEARCH_RESULT_LIMIT,
    SUPPORTED_PUBLISHERS,
    DuckDuckGoHtmlSearcher,
    PageContentFetcher,
    PublisherPageSearcher,
    _clean_text,
    _coerce_http_url,
    _extract_html_title,
    _extract_isbn_candidates,
    _extract_json_ld_record,
    _is_allowed_domain,
    _rank_candidate_urls,
    _run_with_retry,
    match_publisher_profile,
)
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.retailer_pages import SUPPORTED_RETAILERS

WebSearchStatusCallback = Callable[[str], None]

TITLE_CATALOG_ARTIFACT_PATTERN = re.compile(r"\[[^\]]+\]", re.IGNORECASE)
EDITORIAL_CATALOG_ARTIFACT_PATTERN = re.compile(r"[\[\]]|,\s")
MAX_EXCERPT_CHARS = 2200
DEFAULT_DOMAIN_GROUP_SIZE = 4
WEB_SEARCH_SOURCE_NAME = "web_search"
OFFICIAL_WEB_SEARCH_SOURCE_NAME = "web_search_official"


def _chunked(values: tuple[str, ...], chunk_size: int) -> list[tuple[str, ...]]:
    iterator = iter(values)
    chunks: list[tuple[str, ...]] = []
    while chunk := tuple(islice(iterator, chunk_size)):
        chunks.append(chunk)
    return chunks


def _dedupe_groups(groups: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
    deduped: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()

    for group in groups:
        normalized = tuple(dict.fromkeys(domain.casefold() for domain in group))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(group)

    return deduped


def _publisher_domains() -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            domain
            for profile in SUPPORTED_PUBLISHERS
            for domain in profile.domains
        )
    )


def _retailer_domains() -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            domain
            for profile in SUPPORTED_RETAILERS
            for domain in profile.domains
        )
    )


def _is_publisher_domain(domain: str) -> bool:
    normalized_domain = domain.casefold()
    return any(
        normalized_domain == candidate.casefold()
        or normalized_domain.endswith(f".{candidate.casefold()}")
        for candidate in _publisher_domains()
    )


def _is_retailer_domain(domain: str) -> bool:
    normalized_domain = domain.casefold()
    return any(
        normalized_domain == candidate.casefold()
        or normalized_domain.endswith(f".{candidate.casefold()}")
        for candidate in _retailer_domains()
    )


def _catalog_like_title(value: str | None) -> bool:
    if value is None:
        return False
    return bool(TITLE_CATALOG_ARTIFACT_PATTERN.search(value))


def _catalog_like_editorial(value: str | None) -> bool:
    if value is None:
        return False
    return bool(EDITORIAL_CATALOG_ARTIFACT_PATTERN.search(value))


def _needs_web_search_fallback(result: FetchResult) -> bool:
    if result.record is None:
        return True

    record = result.record
    return (
        not bool((record.title or "").strip())
        or not bool((record.author or "").strip())
        or not bool((record.editorial or "").strip())
    )


def _search_domain_groups(record: SourceBookRecord | None) -> list[tuple[str, ...]]:
    groups: list[tuple[str, ...]] = []

    if record is not None:
        matched_profile = match_publisher_profile(record.editorial)
        if matched_profile is not None:
            groups.append(matched_profile.domains)

    groups.extend(_chunked(_retailer_domains(), DEFAULT_DOMAIN_GROUP_SIZE))
    groups.extend(_chunked(_publisher_domains(), DEFAULT_DOMAIN_GROUP_SIZE))
    return _dedupe_groups(groups)


def _search_queries(record: SourceBookRecord) -> list[str]:
    return [f'"{record.isbn}"']


def _build_evidence_excerpt(html: str, isbn: str) -> str:
    parts: list[str] = []
    page_title = _extract_html_title(html)
    if page_title:
        parts.append(f"HTML title: {page_title}")

    json_ld_record = _extract_json_ld_record(html, isbn)
    if json_ld_record is not None:
        parts.extend(
            [
                f"JSON-LD title: {json_ld_record.title or ''}",
                f"JSON-LD subtitle: {json_ld_record.subtitle or ''}",
                f"JSON-LD author: {json_ld_record.author or ''}",
                f"JSON-LD editorial: {json_ld_record.editorial or ''}",
            ]
        )

    cleaned_text = _clean_text(html)
    if cleaned_text:
        parts.append(f"Visible text: {cleaned_text[:MAX_EXCERPT_CHARS]}")

    return "\n".join(part for part in parts if part.strip())


def _web_supporting_documents(
    extraction: WebSearchBibliographicExtraction,
    field_name: str,
    documents: list[WebSearchEvidenceDocument],
) -> list[WebSearchEvidenceDocument]:
    indexes = set(extraction.support.get(field_name, []))
    return [document for document in documents if document.index in indexes]


def _field_confidence_from_support(documents: list[WebSearchEvidenceDocument]) -> float:
    if not documents:
        return 0.0

    distinct_domains = {document.domain.casefold() for document in documents}
    if any(_is_publisher_domain(document.domain) for document in documents):
        return 0.98
    if len(distinct_domains) >= 2:
        return 0.9
    if any(_is_retailer_domain(document.domain) for document in documents):
        return 0.84
    return 0.75


def _field_support_is_sufficient(
    extraction: WebSearchBibliographicExtraction,
    field_name: str,
    documents: list[WebSearchEvidenceDocument],
) -> bool:
    supporting_documents = _web_supporting_documents(extraction, field_name, documents)
    if not supporting_documents:
        return False

    if any(_is_publisher_domain(document.domain) for document in supporting_documents):
        return True

    distinct_domains = {document.domain.casefold() for document in supporting_documents}
    if len(distinct_domains) >= 2:
        return True

    return extraction.confidence >= 0.92 and any(
        _is_retailer_domain(document.domain) for document in supporting_documents
    )


def _primary_support_document(
    extraction: WebSearchBibliographicExtraction,
    field_name: str,
    documents: list[WebSearchEvidenceDocument],
) -> WebSearchEvidenceDocument | None:
    supporting_documents = _web_supporting_documents(extraction, field_name, documents)
    if not supporting_documents:
        return None

    publisher_documents = [
        document for document in supporting_documents if _is_publisher_domain(document.domain)
    ]
    if publisher_documents:
        return publisher_documents[0]

    return supporting_documents[0]


def _serialize_evidence_payload(
    extraction: WebSearchBibliographicExtraction,
    documents: list[WebSearchEvidenceDocument],
) -> str:
    payload = {
        "confidence": extraction.confidence,
        "issues": extraction.issues,
        "explanation": extraction.explanation,
        "support": extraction.support,
        "documents": [
            {
                "index": document.index,
                "url": str(document.url),
                "domain": document.domain,
                "page_title": document.page_title,
            }
            for document in documents
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _build_extracted_record(
    source_record: SourceBookRecord,
    extraction: WebSearchBibliographicExtraction,
    documents: list[WebSearchEvidenceDocument],
) -> SourceBookRecord | None:
    field_sources: dict[str, str] = {}
    field_confidence: dict[str, float] = {}
    extracted_title: str | None = None
    extracted_subtitle: str | None = None
    extracted_author: str | None = None
    extracted_editorial: str | None = None

    for field_name in ("title", "subtitle", "author", "editorial"):
        value = getattr(extraction, field_name)
        if value is None:
            continue
        if not _field_support_is_sufficient(extraction, field_name, documents):
            continue

        support_document = _primary_support_document(extraction, field_name, documents)
        if support_document is None:
            continue

        source_name = (
            OFFICIAL_WEB_SEARCH_SOURCE_NAME
            if _is_publisher_domain(support_document.domain)
            else WEB_SEARCH_SOURCE_NAME
        )
        if field_name == "title":
            extracted_title = value
        elif field_name == "subtitle":
            extracted_subtitle = value
        elif field_name == "author":
            extracted_author = value
        elif field_name == "editorial":
            extracted_editorial = value
        field_sources[field_name] = f"{source_name}:{support_document.domain}"
        field_confidence[field_name] = _field_confidence_from_support(
            _web_supporting_documents(extraction, field_name, documents)
        )

    if not any((extracted_title, extracted_subtitle, extracted_author, extracted_editorial)):
        return None

    extracted_source_url = None
    support_document = (
        _primary_support_document(extraction, "editorial", documents)
        or _primary_support_document(extraction, "author", documents)
        or _primary_support_document(extraction, "title", documents)
    )
    if support_document is not None:
        extracted_source_url = _coerce_http_url(str(support_document.url))
        field_sources["source_url"] = f"{WEB_SEARCH_SOURCE_NAME}:{support_document.domain}"
        field_confidence["source_url"] = _field_confidence_from_support([support_document])

    raw_source_payload = _serialize_evidence_payload(extraction, documents)

    return SourceBookRecord(
        source_name=WEB_SEARCH_SOURCE_NAME,
        isbn=source_record.isbn,
        source_url=extracted_source_url,
        raw_source_payload=raw_source_payload,
        title=extracted_title,
        subtitle=extracted_subtitle,
        author=extracted_author,
        editorial=extracted_editorial,
        field_sources=field_sources,
        field_confidence=field_confidence,
    )


def _should_override_catalog_artifact(
    field_name: str,
    existing_value: str | None,
    extracted_value: str | None,
    extracted_confidence: float,
) -> bool:
    if existing_value is None or extracted_value is None:
        return False

    if field_name in {"title", "subtitle"}:
        return (
            _catalog_like_title(existing_value)
            and not _catalog_like_title(extracted_value)
            and extracted_confidence >= 0.9
        )

    if field_name == "editorial":
        return (
            _catalog_like_editorial(existing_value)
            and not _catalog_like_editorial(extracted_value)
            and extracted_confidence >= 0.9
        )

    return False


def _apply_web_search_record(
    existing_record: SourceBookRecord,
    extracted_record: SourceBookRecord,
) -> SourceBookRecord:
    merged_record = merge_source_records([existing_record, extracted_record])
    field_sources = dict(merged_record.field_sources)
    field_confidence = dict(merged_record.field_confidence)
    updates: dict[str, object] = {
        "raw_source_payload": (
            extracted_record.raw_source_payload or existing_record.raw_source_payload
        ),
    }

    for field_name in ("title", "subtitle", "editorial"):
        existing_value = getattr(existing_record, field_name)
        extracted_value = getattr(extracted_record, field_name)
        extracted_field_confidence = extracted_record.field_confidence.get(field_name, 0.0)
        if not _should_override_catalog_artifact(
            field_name,
            existing_value,
            extracted_value,
            extracted_field_confidence,
        ):
            continue

        updates[field_name] = extracted_value
        if field_name in extracted_record.field_sources:
            field_sources[field_name] = extracted_record.field_sources[field_name]
        if field_name in extracted_record.field_confidence:
            field_confidence[field_name] = extracted_record.field_confidence[field_name]

    if extracted_record.source_url is not None:
        updates["source_url"] = extracted_record.source_url
        if "source_url" in extracted_record.field_sources:
            field_sources["source_url"] = extracted_record.field_sources["source_url"]
        if "source_url" in extracted_record.field_confidence:
            field_confidence["source_url"] = extracted_record.field_confidence["source_url"]

    updates["field_sources"] = field_sources
    updates["field_confidence"] = field_confidence
    return merged_record.model_copy(update=updates)


def _seed_record(fetch_result: FetchResult) -> SourceBookRecord:
    if fetch_result.record is not None:
        return fetch_result.record

    return SourceBookRecord(
        source_name="fetch_error",
        isbn=fetch_result.isbn,
    )


def _merge_issue_codes(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for code in group:
            if code in seen:
                continue
            seen.add(code)
            merged.append(code)
    return merged


class _DefaultPageFetcher(PageContentFetcher):
    def __init__(self, timeout_seconds: float, client: httpx.Client | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.client = client

    def fetch_text(self, url: str) -> str | None:
        client = self.client or httpx.Client()
        response = client.get(
            url,
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text


def augment_fetch_results_with_web_search(
    fetch_results: list[FetchResult],
    timeout_seconds: float,
    extractor: BibliographicEvidenceExtractor | None,
    searcher: PublisherPageSearcher | None = None,
    page_fetcher: PageContentFetcher | None = None,
    on_status_update: WebSearchStatusCallback | None = None,
    max_retries: int = 1,
    backoff_seconds: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
    max_pages_per_record: int = 3,
    max_search_attempts_per_record: int = 6,
    max_fetch_attempts_per_record: int = 4,
) -> list[FetchResult]:
    if extractor is None:
        return fetch_results

    targeted_results = [result for result in fetch_results if _needs_web_search_fallback(result)]
    if not targeted_results:
        return fetch_results

    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        active_searcher = searcher or DuckDuckGoHtmlSearcher(timeout_seconds, client=client)
        active_page_fetcher = page_fetcher or _DefaultPageFetcher(timeout_seconds, client=client)
        augmented_results: list[FetchResult] = []

        if on_status_update is not None:
            on_status_update(
                "Stage: searching trusted web sources "
                f"for {len(targeted_results)} Stage 1 records"
            )

        targeted_index = 0
        for index, fetch_result in enumerate(fetch_results, start=1):
            if not _needs_web_search_fallback(fetch_result):
                augmented_results.append(fetch_result)
                continue

            targeted_index += 1
            source_record = _seed_record(fetch_result)
            if on_status_update is not None:
                on_status_update(
                    "Web search fallback "
                    f"{targeted_index}/{len(targeted_results)}: {source_record.isbn}"
                )

            issue_codes: list[str] = []
            documents: list[WebSearchEvidenceDocument] = []
            seen_urls: set[str] = set()
            search_attempts = 0
            fetch_attempts = 0

            for query in _search_queries(source_record):
                if len(documents) >= max_pages_per_record:
                    break

                for allowed_domains in _search_domain_groups(source_record):
                    if search_attempts >= max_search_attempts_per_record:
                        break

                    search_attempts += 1
                    candidate_urls, search_issue_codes = _run_with_retry(
                        lambda: active_searcher.search(query, allowed_domains, SEARCH_RESULT_LIMIT),
                        "web_search_search",
                        max_retries,
                        backoff_seconds,
                        sleep,
                    )
                    issue_codes = _merge_issue_codes(issue_codes, search_issue_codes)
                    if candidate_urls is None:
                        continue

                    for candidate_url in _rank_candidate_urls(candidate_urls, source_record):
                        if len(documents) >= max_pages_per_record:
                            break
                        if (
                            candidate_url in seen_urls
                            or not _is_allowed_domain(candidate_url, allowed_domains)
                        ):
                            continue
                        if fetch_attempts >= max_fetch_attempts_per_record:
                            break

                        fetch_attempts += 1
                        seen_urls.add(candidate_url)
                        page_html, fetch_issue_codes = _run_with_retry(
                            lambda: active_page_fetcher.fetch_text(candidate_url),
                            "web_search_fetch",
                            max_retries,
                            backoff_seconds,
                            sleep,
                        )
                        issue_codes = _merge_issue_codes(issue_codes, fetch_issue_codes)
                        if page_html is None:
                            continue

                        normalized_isbns = _extract_isbn_candidates(page_html)
                        if source_record.isbn not in normalized_isbns:
                            continue

                        hostname = urlparse(candidate_url).hostname or ""
                        candidate_http_url = _coerce_http_url(candidate_url)
                        if candidate_http_url is None:
                            continue
                        documents.append(
                            WebSearchEvidenceDocument(
                                index=len(documents),
                                url=candidate_http_url,
                                domain=hostname,
                                page_title=_extract_html_title(page_html),
                                excerpt=_build_evidence_excerpt(page_html, source_record.isbn),
                            )
                        )

                    if (
                        len(documents) >= max_pages_per_record
                        or fetch_attempts >= max_fetch_attempts_per_record
                    ):
                        break

            if not documents:
                augmented_results.append(
                    fetch_result.model_copy(
                        update={
                            "issue_codes": _merge_issue_codes(
                                fetch_result.issue_codes,
                                issue_codes,
                                [no_match_issue_code("web_search")],
                            )
                        }
                    )
                )
                continue

            extraction = extractor.extract(source_record, documents)
            if extraction is None or "extractor_low_confidence" in extraction.issues:
                augmented_results.append(
                    fetch_result.model_copy(
                        update={
                            "issue_codes": _merge_issue_codes(
                                fetch_result.issue_codes,
                                issue_codes,
                                ["WEB_SEARCH_EXTRACTION_UNAVAILABLE"],
                            )
                        }
                    )
                )
                continue

            extracted_record = _build_extracted_record(source_record, extraction, documents)
            if extracted_record is None:
                augmented_results.append(
                    fetch_result.model_copy(
                        update={
                            "issue_codes": _merge_issue_codes(
                                fetch_result.issue_codes,
                                issue_codes,
                                ["WEB_SEARCH_EXTRACTION_NO_GAIN"],
                            )
                        }
                    )
                )
                continue

            if fetch_result.record is None:
                augmented_results.append(
                    fetch_result.model_copy(
                        update={
                            "record": extracted_record,
                            "issue_codes": _merge_issue_codes(
                                fetch_result.issue_codes,
                                issue_codes,
                            ),
                        }
                    )
                )
                continue

            augmented_results.append(
                fetch_result.model_copy(
                    update={
                        "record": _apply_web_search_record(fetch_result.record, extracted_record),
                        "issue_codes": _merge_issue_codes(fetch_result.issue_codes, issue_codes),
                    }
                )
            )

        return augmented_results
