import re
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from book_store_assistant.sources.issues import no_match_issue_code
from book_store_assistant.sources.merge import merge_source_records
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.publisher_pages import (
    SEARCH_RESULT_LIMIT,
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
)
from book_store_assistant.sources.results import FetchResult

RetailerStatusCallback = Callable[[str], None]
RETAILER_EDITORIAL_CACHE_KEY = "retailer_editorial_lookup_v1"

AUTHOR_LABEL_PATTERN = re.compile(
    r"(?:autor(?:es)?|author)\s*[:|]\s*([^\n|]+)",
    re.IGNORECASE,
)
EDITORIAL_LABEL_PATTERN = re.compile(
    r"(?:editorial|editor|publisher|sello)\s*[:|]\s*([^\n|]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RetailerProfile:
    key: str
    domains: tuple[str, ...]


SUPPORTED_RETAILERS = (
    RetailerProfile(
        key="casa_del_libro",
        domains=("casadellibro.com",),
    ),
    RetailerProfile(
        key="libreria_nacional",
        domains=("librerianacional.com",),
    ),
    RetailerProfile(
        key="fnac",
        domains=("fnac.es",),
    ),
    RetailerProfile(
        key="buscalibre",
        domains=("buscalibre.com",),
    ),
    RetailerProfile(
        key="panamericana",
        domains=("panamericana.com.co",),
    ),
    RetailerProfile(
        key="agapea",
        domains=("agapea.com",),
    ),
    RetailerProfile(
        key="todostuslibros",
        domains=("todostuslibros.com",),
    ),
)


def _extract_labeled_value(html: str, pattern: re.Pattern[str]) -> str | None:
    text = _clean_text(html)
    match = pattern.search(text)
    if match is None:
        return None
    value = match.group(1).strip(" .|")
    return value or None


def extract_retailer_page_record(
    html: str,
    page_url: str,
    isbn: str,
    profile: RetailerProfile,
) -> SourceBookRecord | None:
    if isbn not in _extract_isbn_candidates(html):
        return None

    json_ld_record = _extract_json_ld_record(html, isbn)
    if json_ld_record is not None and json_ld_record.editorial:
        return SourceBookRecord(
            source_name=f"retailer_page:{profile.key}",
            isbn=isbn,
            source_url=_coerce_http_url(page_url),
            title=json_ld_record.title,
            author=json_ld_record.author,
            editorial=json_ld_record.editorial,
        )

    title = _extract_html_title(html)
    author = _extract_labeled_value(html, AUTHOR_LABEL_PATTERN)
    editorial = _extract_labeled_value(html, EDITORIAL_LABEL_PATTERN)
    if editorial is None:
        return None

    return SourceBookRecord(
        source_name=f"retailer_page:{profile.key}",
        isbn=isbn,
        source_url=_coerce_http_url(page_url),
        title=title,
        author=author,
        editorial=editorial,
    )


def _needs_retailer_editorial_lookup(record: SourceBookRecord) -> bool:
    return not record.editorial


def build_retailer_search_query(record: SourceBookRecord) -> str:
    query_parts = [f'"{record.isbn}"']
    if record.title:
        query_parts.append(f'"{record.title}"')
    if record.author:
        primary_author = record.author.split(",", maxsplit=1)[0].strip()
        if primary_author:
            query_parts.append(f'"{primary_author}"')
    return " ".join(query_parts)


def build_retailer_search_queries(record: SourceBookRecord) -> list[str]:
    queries = [build_retailer_search_query(record), f'"{record.isbn}"']

    if record.title:
        queries.append(" ".join([f'"{record.isbn}"', f'"{record.title}"']))

    if record.author:
        primary_author = record.author.split(",", maxsplit=1)[0].strip()
        if primary_author:
            queries.append(" ".join([f'"{record.isbn}"', f'"{primary_author}"']))

    deduplicated: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized_query = " ".join(query.split()).strip()
        if not normalized_query or normalized_query in seen:
            continue
        seen.add(normalized_query)
        deduplicated.append(normalized_query)

    return deduplicated


def apply_retailer_editorial_record(
    existing_record: SourceBookRecord,
    retailer_record: SourceBookRecord,
) -> SourceBookRecord:
    merged_record = merge_source_records([existing_record, retailer_record])
    field_sources = dict(merged_record.field_sources)
    field_confidence = dict(merged_record.field_confidence)

    if not existing_record.editorial and retailer_record.editorial:
        field_sources["editorial"] = retailer_record.source_name
        field_confidence["editorial"] = 0.55

    return merged_record.model_copy(
        update={
            "field_sources": field_sources,
            "field_confidence": field_confidence,
        }
    )


def augment_fetch_results_with_retailer_editorials(
    fetch_results: list[FetchResult],
    timeout_seconds: float,
    searcher: PublisherPageSearcher | None = None,
    page_fetcher: PageContentFetcher | None = None,
    on_status_update: RetailerStatusCallback | None = None,
    max_retries: int = 2,
    backoff_seconds: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> list[FetchResult]:
    active_searcher = searcher or DuckDuckGoHtmlSearcher(timeout_seconds)
    active_page_fetcher = page_fetcher or _DefaultRetailerPageFetcher(timeout_seconds)
    augmented_results: list[FetchResult] = []

    if on_status_update is not None:
        on_status_update(
            f"Stage: checking retailer pages for {len(fetch_results)} fetched records"
        )

    for index, fetch_result in enumerate(fetch_results, start=1):
        record = fetch_result.record
        if record is None or not _needs_retailer_editorial_lookup(record):
            augmented_results.append(fetch_result)
            continue

        retailer_issue_codes: list[str] = []
        retailer_record: SourceBookRecord | None = None

        if on_status_update is not None:
            on_status_update(
                f"Retailer editorial lookup {index}/{len(fetch_results)}: {record.isbn}"
            )

        for profile in SUPPORTED_RETAILERS:
            candidate_urls: list[str] = []
            for query in build_retailer_search_queries(record):
                query_candidate_urls, search_issue_codes = _run_with_retry(
                    lambda query=query, domains=profile.domains: active_searcher.search(
                        query,
                        domains,
                        limit=SEARCH_RESULT_LIMIT,
                    ),
                    "retailer_page_search",
                    max_retries=max_retries,
                    backoff_seconds=backoff_seconds,
                    sleep=sleep,
                )
                if query_candidate_urls is None:
                    retailer_issue_codes.extend(
                        code for code in search_issue_codes if code not in retailer_issue_codes
                    )
                    continue

                for candidate_url in query_candidate_urls:
                    if candidate_url not in candidate_urls:
                        candidate_urls.append(candidate_url)

                if candidate_urls:
                    break

            if not candidate_urls:
                continue

            for candidate_url in _rank_candidate_urls(candidate_urls, record):
                if not _is_allowed_domain(candidate_url, profile.domains):
                    continue

                page_html, fetch_issue_codes = _run_with_retry(
                    lambda: active_page_fetcher.fetch_text(candidate_url),
                    "retailer_page_fetch",
                    max_retries=max_retries,
                    backoff_seconds=backoff_seconds,
                    sleep=sleep,
                )
                if page_html is None:
                    retailer_issue_codes.extend(
                        code for code in fetch_issue_codes if code not in retailer_issue_codes
                    )
                    continue

                retailer_record = extract_retailer_page_record(
                    page_html,
                    candidate_url,
                    record.isbn,
                    profile,
                )
                if retailer_record is not None:
                    break

            if retailer_record is not None:
                break

        if retailer_record is None:
            augmented_results.append(
                fetch_result.model_copy(
                    update={
                        "issue_codes": [
                            *fetch_result.issue_codes,
                            *(
                                code
                                for code in retailer_issue_codes
                                if code not in fetch_result.issue_codes
                            ),
                            *(
                                [no_match_issue_code("retailer_page_editorial")]
                                if no_match_issue_code("retailer_page_editorial")
                                not in fetch_result.issue_codes
                                and no_match_issue_code("retailer_page_editorial")
                                not in retailer_issue_codes
                                else []
                            ),
                        ]
                    }
                )
            )
            continue

        augmented_results.append(
            fetch_result.model_copy(
                update={
                    "record": apply_retailer_editorial_record(record, retailer_record)
                }
            )
        )

    return augmented_results


class _DefaultRetailerPageFetcher:
    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_text(self, url: str) -> str | None:
        response = httpx.get(
            url,
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text
