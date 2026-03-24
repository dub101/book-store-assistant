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
from book_store_assistant.sources.diagnostics import changed_record_fields, with_diagnostic
from book_store_assistant.sources.issues import no_match_issue_code
from book_store_assistant.sources.merge import merge_source_records
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.publisher_pages import (
    SUPPORTED_PUBLISHERS,
    _clean_text,
    _coerce_http_url,
    _extract_html_title,
    _extract_isbn_candidates,
    _extract_json_ld_record,
    _normalize_text,
    _rank_candidate_urls,
    _run_with_retry,
    match_publisher_profile,
)
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.retailer_pages import SUPPORTED_RETAILERS
from book_store_assistant.sources.search_backend import (
    DEFAULT_BROWSER_HEADERS,
    SEARCH_RESULT_LIMIT,
    PageContentFetcher,
    SearchBackend,
    _is_allowed_domain,
    build_default_search_backend,
)
from book_store_assistant.sources.search_queries import (
    build_contextual_isbn_queries,
    build_editorial_discovery_queries,
    clean_query_text,
    editorial_query_terms,
)

WebSearchStatusCallback = Callable[[str], None]
SearchCompletionPredicate = Callable[[FetchResult], bool]
SearchQueryBuilder = Callable[[SourceBookRecord], list[str]]

TITLE_CATALOG_ARTIFACT_PATTERN = re.compile(r"\[[^\]]+\]", re.IGNORECASE)
EDITORIAL_CATALOG_ARTIFACT_PATTERN = re.compile(r"[\[\]]|,\s")
MAX_EXCERPT_CHARS = 2200
DEFAULT_DOMAIN_GROUP_SIZE = 4
WEB_SEARCH_SOURCE_NAME = "web_search"
OFFICIAL_WEB_SEARCH_SOURCE_NAME = "web_search_official"
DEFAULT_WEB_SEARCH_FIELDS = ("title", "subtitle", "author", "editorial")
EDITORIAL_DISCOVERY_FIELDS = ("editorial",)
EDITORIAL_SEARCH_RESULT_LIMIT = 10


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
        if not group:
            if group in seen:
                continue
            seen.add(group)
            deduped.append(group)
            continue

        normalized = tuple(dict.fromkeys(domain.casefold() for domain in group))
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(group)

    return deduped


def _interleave_groups(
    primary_groups: list[tuple[str, ...]],
    secondary_groups: list[tuple[str, ...]],
) -> list[tuple[str, ...]]:
    interleaved: list[tuple[str, ...]] = []
    limit = max(len(primary_groups), len(secondary_groups))

    for index in range(limit):
        if index < len(primary_groups):
            interleaved.append(primary_groups[index])
        if index < len(secondary_groups):
            interleaved.append(secondary_groups[index])

    return interleaved


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


def _all_trusted_domains() -> tuple[str, ...]:
    return tuple(dict.fromkeys((*_publisher_domains(), *_retailer_domains())))


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


def _needs_web_search_completion(result: FetchResult) -> bool:
    if result.record is None:
        return True

    record = result.record
    return (
        not bool((record.title or "").strip())
        or not bool((record.author or "").strip())
        or not bool((record.editorial or "").strip())
    )


def _needs_editorial_discovery(result: FetchResult) -> bool:
    if result.record is None:
        return True

    return not bool((result.record.editorial or "").strip())


def _search_domain_groups(record: SourceBookRecord | None) -> list[tuple[str, ...]]:
    groups: list[tuple[str, ...]] = []
    publisher_groups = _chunked(_publisher_domains(), DEFAULT_DOMAIN_GROUP_SIZE)
    retailer_groups = _chunked(_retailer_domains(), DEFAULT_DOMAIN_GROUP_SIZE)

    if record is not None:
        matched_profile = match_publisher_profile(record.editorial)
        if matched_profile is not None:
            groups.append(matched_profile.domains)

    groups.extend(_interleave_groups(publisher_groups, retailer_groups))
    all_trusted_domains = _all_trusted_domains()
    if all_trusted_domains:
        groups.append(all_trusted_domains)
    return _dedupe_groups(groups)


def _search_queries(
    record: SourceBookRecord,
    query_builder: SearchQueryBuilder | None = None,
) -> list[str]:
    builder = query_builder or build_contextual_isbn_queries
    return builder(record)


def _search_attempt_plan(
    source_record: SourceBookRecord,
    query_builder: SearchQueryBuilder | None = None,
    search_result_limit: int = SEARCH_RESULT_LIMIT,
    include_open_web_stage: bool = True,
) -> list[tuple[str, tuple[str, ...], int]]:
    queries = _search_queries(source_record, query_builder=query_builder)
    if not queries:
        return []

    matched_profile = match_publisher_profile(source_record.editorial)
    matched_domains = matched_profile.domains if matched_profile is not None else ()
    official_groups = _chunked(_publisher_domains(), DEFAULT_DOMAIN_GROUP_SIZE)
    retailer_groups = _chunked(_retailer_domains(), DEFAULT_DOMAIN_GROUP_SIZE)
    trusted_groups = _search_domain_groups(source_record)
    discovery_queries = queries[: min(3, len(queries))]
    refinement_queries = queries[min(3, len(queries)) :] or discovery_queries

    attempts: list[tuple[str, tuple[str, ...], int]] = []
    seen: set[tuple[str, tuple[str, ...], int]] = set()

    search_stages: list[tuple[list[str], list[tuple[str, ...]], int]] = []
    if include_open_web_stage:
        search_stages.append(
            (
                discovery_queries[:2] or discovery_queries,
                _dedupe_groups(
                    [tuple(), matched_domains] if matched_domains else [tuple()]
                ),
                search_result_limit,
            )
        )
    search_stages.extend(
        [
            (
                discovery_queries,
                _dedupe_groups(
                    ([matched_domains] if matched_domains else []) + official_groups[:2]
                ),
                search_result_limit,
            ),
            (
                discovery_queries[:2] or discovery_queries,
                retailer_groups[:2],
                search_result_limit,
            ),
            (
                refinement_queries,
                trusted_groups,
                search_result_limit,
            ),
        ]
    )

    for query_group, domain_groups, result_limit in search_stages:
        for allowed_domains in domain_groups:
            for query in query_group:
                attempt = (query, allowed_domains, result_limit)
                if attempt in seen:
                    continue
                seen.add(attempt)
                attempts.append(attempt)

    return attempts


def _url_context_score(url: str, source_record: SourceBookRecord) -> tuple[int, int, int, int, int]:
    hostname = (urlparse(url).hostname or "").casefold()
    url_text = _normalize_text(url)
    matched_profile = match_publisher_profile(source_record.editorial)
    title = _normalized_context_value(source_record.title)
    author = _normalized_context_value(source_record.author)
    editorial_terms = [
        _normalize_text(term)
        for term in editorial_query_terms(source_record.editorial)
        if _normalize_text(term)
    ]

    matched_domain = int(
        matched_profile is not None
        and any(
            hostname == domain.casefold() or hostname.endswith(f".{domain.casefold()}")
            for domain in matched_profile.domains
        )
    )
    trusted_domain = (
        2
        if _is_publisher_domain(hostname)
        else 1
        if _is_retailer_domain(hostname)
        else 0
    )
    isbn_in_url = int(source_record.isbn in url)
    contextual_hits = 0
    if title is not None and title in url_text:
        contextual_hits += 2
    if author is not None and author in url_text:
        contextual_hits += 1
    if editorial_terms and any(term in url_text for term in editorial_terms[:2]):
        contextual_hits += 1

    return (
        matched_domain,
        trusted_domain,
        isbn_in_url,
        contextual_hits,
        -len(url),
    )


def _rank_web_candidate_urls(
    candidate_urls: list[str],
    source_record: SourceBookRecord,
) -> list[str]:
    seeded_rank = _rank_candidate_urls(candidate_urls, source_record)
    return sorted(
        seeded_rank,
        key=lambda candidate_url: _url_context_score(candidate_url, source_record),
        reverse=True,
    )


def _normalized_context_value(value: str | None) -> str | None:
    cleaned = clean_query_text(value)
    if cleaned is None:
        return None

    normalized = _normalize_text(cleaned)
    return normalized or None


def _contextual_page_match_score(
    html: str,
    page_url: str,
    source_record: SourceBookRecord,
) -> int:
    page_title = _normalize_text(_extract_html_title(html) or "")
    page_text = _normalize_text(_clean_text(html))
    page_url_text = _normalize_text(page_url)
    score = 0

    title = _normalized_context_value(source_record.title)
    author = _normalized_context_value(source_record.author)
    editorial_terms = [
        _normalize_text(term)
        for term in editorial_query_terms(source_record.editorial)[:2]
        if _normalize_text(term)
    ]

    if title is not None:
        if title in page_title:
            score += 3
        elif title in page_text or title in page_url_text:
            score += 2

    if author is not None and (
        author in page_title or author in page_text or author in page_url_text
    ):
        score += 1

    if editorial_terms and any(
        editorial in page_title or editorial in page_text or editorial in page_url_text
        for editorial in editorial_terms
    ):
        score += 1

    return score


def _supports_contextual_page_match(
    html: str,
    page_url: str,
    source_record: SourceBookRecord,
) -> bool:
    hostname = urlparse(page_url).hostname or ""
    score = _contextual_page_match_score(html, page_url, source_record)

    if _is_publisher_domain(hostname):
        return score >= 3

    if _is_retailer_domain(hostname):
        return score >= 4

    return score >= 5


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

    if extraction.confidence >= 0.95 and any(
        document.isbn_present for document in supporting_documents
    ):
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
    *,
    target_fields: tuple[str, ...] = DEFAULT_WEB_SEARCH_FIELDS,
) -> SourceBookRecord | None:
    field_sources: dict[str, str] = {}
    field_confidence: dict[str, float] = {}
    extracted_title: str | None = None
    extracted_subtitle: str | None = None
    extracted_author: str | None = None
    extracted_editorial: str | None = None

    for field_name in target_fields:
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
            headers=DEFAULT_BROWSER_HEADERS,
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text


def augment_fetch_results_with_web_search(
    fetch_results: list[FetchResult],
    timeout_seconds: float,
    extractor: BibliographicEvidenceExtractor | None,
    searcher: SearchBackend | None = None,
    page_fetcher: PageContentFetcher | None = None,
    on_status_update: WebSearchStatusCallback | None = None,
    max_retries: int = 1,
    backoff_seconds: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
    max_pages_per_record: int = 3,
    max_search_attempts_per_record: int = 6,
    max_fetch_attempts_per_record: int = 4,
    allow_contextual_matches: bool = False,
    status_label: str = "general",
    completion_predicate: SearchCompletionPredicate | None = None,
    query_builder: SearchQueryBuilder | None = None,
    target_fields: tuple[str, ...] = DEFAULT_WEB_SEARCH_FIELDS,
    search_result_limit: int = SEARCH_RESULT_LIMIT,
    include_open_web_stage: bool = True,
) -> list[FetchResult]:
    if extractor is None:
        return fetch_results

    active_completion_predicate = completion_predicate or _needs_web_search_completion
    targeted_results = [
        result for result in fetch_results if active_completion_predicate(result)
    ]
    if not targeted_results:
        return fetch_results

    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        active_searcher = searcher or build_default_search_backend(
            timeout_seconds,
            client=client,
        )
        active_page_fetcher = page_fetcher or _DefaultPageFetcher(timeout_seconds, client=client)
        augmented_results: list[FetchResult] = []

        if on_status_update is not None:
            on_status_update(
                "Stage: searching trusted web sources "
                f"for {len(targeted_results)} Stage 1 records ({status_label})"
            )

        targeted_index = 0
        for index, fetch_result in enumerate(fetch_results, start=1):
            if not active_completion_predicate(fetch_result):
                augmented_results.append(fetch_result)
                continue

            targeted_index += 1
            source_record = _seed_record(fetch_result)
            if on_status_update is not None:
                on_status_update(
                    f"Web search {status_label} "
                    f"{targeted_index}/{len(targeted_results)}: {source_record.isbn}"
                )

            issue_codes: list[str] = []
            documents: list[WebSearchEvidenceDocument] = []
            seen_urls: set[str] = set()
            fetched_domains: list[str] = []
            attempted_search_queries: list[str] = []
            attempted_search_domains: list[list[str]] = []
            candidate_urls_seen: list[str] = []
            search_attempts = 0
            fetch_attempts = 0

            for query, allowed_domains, result_limit in _search_attempt_plan(
                source_record,
                query_builder=query_builder,
                search_result_limit=search_result_limit,
                include_open_web_stage=include_open_web_stage,
            ):
                if len(documents) >= max_pages_per_record:
                    break

                if search_attempts >= max_search_attempts_per_record:
                    break

                search_attempts += 1
                attempted_search_queries.append(query)
                attempted_search_domains.append(list(allowed_domains))
                candidate_urls, search_issue_codes = _run_with_retry(
                    lambda: active_searcher.search(query, allowed_domains, result_limit),
                    "web_search_search",
                    max_retries,
                    backoff_seconds,
                    sleep,
                )
                issue_codes = _merge_issue_codes(issue_codes, search_issue_codes)
                if candidate_urls is None:
                    continue
                for candidate_url in candidate_urls:
                    if candidate_url not in seen_urls and candidate_url not in candidate_urls_seen:
                        candidate_urls_seen.append(candidate_url)

                for candidate_url in _rank_web_candidate_urls(candidate_urls, source_record):
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
                    hostname = (urlparse(candidate_url).hostname or "").casefold()
                    if hostname and hostname not in fetched_domains:
                        fetched_domains.append(hostname)
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
                    isbn_present = source_record.isbn in normalized_isbns
                    if not isbn_present and not (
                        allow_contextual_matches
                        and _supports_contextual_page_match(
                            page_html,
                            candidate_url,
                            source_record,
                        )
                    ):
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
                            isbn_present=isbn_present,
                        )
                    )

                if (
                    len(documents) >= max_pages_per_record
                    or fetch_attempts >= max_fetch_attempts_per_record
                ):
                    break

            if not documents:
                augmented_results.append(
                    with_diagnostic(
                        fetch_result,
                        f"web_search_{status_label}",
                        "completed",
                        web_search_match=False,
                        search_queries=attempted_search_queries,
                        search_domains=attempted_search_domains,
                        search_attempts=search_attempts,
                        candidate_urls=candidate_urls_seen,
                        fetched_domains=fetched_domains,
                        documents_found=0,
                        fetch_attempts=fetch_attempts,
                        issue_codes=issue_codes,
                    ).model_copy(
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
                    with_diagnostic(
                        fetch_result,
                        f"web_search_{status_label}",
                        "completed",
                        web_search_match=True,
                        search_queries=attempted_search_queries,
                        search_domains=attempted_search_domains,
                        search_attempts=search_attempts,
                        candidate_urls=candidate_urls_seen,
                        fetched_domains=fetched_domains,
                        documents_found=len(documents),
                        document_domains=[document.domain for document in documents],
                        fetch_attempts=fetch_attempts,
                        extraction_used=False,
                        extraction_confidence=(
                            extraction.confidence if extraction is not None else None
                        ),
                        extraction_issues=(extraction.issues if extraction is not None else None),
                        issue_codes=issue_codes,
                    ).model_copy(
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

            extracted_record = _build_extracted_record(
                source_record,
                extraction,
                documents,
                target_fields=target_fields,
            )
            if extracted_record is None:
                augmented_results.append(
                    with_diagnostic(
                        fetch_result,
                        f"web_search_{status_label}",
                        "completed",
                        web_search_match=True,
                        search_queries=attempted_search_queries,
                        search_domains=attempted_search_domains,
                        search_attempts=search_attempts,
                        candidate_urls=candidate_urls_seen,
                        fetched_domains=fetched_domains,
                        documents_found=len(documents),
                        document_domains=[document.domain for document in documents],
                        fetch_attempts=fetch_attempts,
                        extraction_used=True,
                        extraction_confidence=extraction.confidence,
                        extraction_issues=extraction.issues,
                        extracted_fields=[],
                        issue_codes=issue_codes,
                    ).model_copy(
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
                changed_fields = changed_record_fields(None, extracted_record)
                augmented_results.append(
                    with_diagnostic(
                        fetch_result,
                        f"web_search_{status_label}",
                        "completed",
                        web_search_match=True,
                        search_queries=attempted_search_queries,
                        search_domains=attempted_search_domains,
                        search_attempts=search_attempts,
                        candidate_urls=candidate_urls_seen,
                        fetched_domains=fetched_domains,
                        documents_found=len(documents),
                        document_domains=[document.domain for document in documents],
                        fetch_attempts=fetch_attempts,
                        extraction_used=True,
                        extraction_confidence=extraction.confidence,
                        extraction_issues=extraction.issues,
                        extracted_fields=changed_fields,
                        changed_fields=changed_fields,
                        issue_codes=issue_codes,
                    ).model_copy(
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

            merged_record = _apply_web_search_record(fetch_result.record, extracted_record)
            changed_fields = changed_record_fields(fetch_result.record, merged_record)
            augmented_results.append(
                with_diagnostic(
                    fetch_result,
                    f"web_search_{status_label}",
                    "completed",
                    web_search_match=True,
                    search_queries=attempted_search_queries,
                    search_domains=attempted_search_domains,
                    search_attempts=search_attempts,
                    candidate_urls=candidate_urls_seen,
                    fetched_domains=fetched_domains,
                    documents_found=len(documents),
                    document_domains=[document.domain for document in documents],
                    fetch_attempts=fetch_attempts,
                    extraction_used=True,
                    extraction_confidence=extraction.confidence,
                    extraction_issues=extraction.issues,
                        extracted_fields=[
                            field_name
                            for field_name in target_fields
                            if getattr(extracted_record, field_name) is not None
                        ],
                    changed_fields=changed_fields,
                    issue_codes=issue_codes,
                ).model_copy(
                    update={
                        "record": merged_record,
                        "issue_codes": _merge_issue_codes(fetch_result.issue_codes, issue_codes),
                    }
                )
            )

        return augmented_results


def augment_fetch_results_with_editorial_search(
    fetch_results: list[FetchResult],
    timeout_seconds: float,
    extractor: BibliographicEvidenceExtractor | None,
    searcher: SearchBackend | None = None,
    page_fetcher: PageContentFetcher | None = None,
    on_status_update: WebSearchStatusCallback | None = None,
    max_retries: int = 1,
    backoff_seconds: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
    max_pages_per_record: int = 3,
    max_search_attempts_per_record: int = 6,
    max_fetch_attempts_per_record: int = 4,
) -> list[FetchResult]:
    return augment_fetch_results_with_web_search(
        fetch_results,
        timeout_seconds=timeout_seconds,
        extractor=extractor,
        searcher=searcher,
        page_fetcher=page_fetcher,
        on_status_update=on_status_update,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
        sleep=sleep,
        max_pages_per_record=max_pages_per_record,
        max_search_attempts_per_record=max_search_attempts_per_record,
        max_fetch_attempts_per_record=max_fetch_attempts_per_record,
        allow_contextual_matches=True,
        status_label="editorial",
        completion_predicate=_needs_editorial_discovery,
        query_builder=build_editorial_discovery_queries,
        target_fields=EDITORIAL_DISCOVERY_FIELDS,
        search_result_limit=EDITORIAL_SEARCH_RESULT_LIMIT,
        include_open_web_stage=False,
    )
