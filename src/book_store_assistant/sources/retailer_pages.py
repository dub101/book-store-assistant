import re
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from book_store_assistant.sources.cache import FetchResultCache
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
RETAILER_EDITORIAL_CACHE_KEY = "retailer_editorial_lookup_v2"

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
        key="agapea",
        domains=("agapea.com",),
    ),
    RetailerProfile(
        key="buscalibre",
        domains=(
            "buscalibre.com",
            "buscalibre.cl",
            "buscalibre.com.co",
            "buscalibre.com.mx",
            "buscalibre.pe",
            "buscalibre.us",
        ),
    ),
    RetailerProfile(
        key="casa_del_libro",
        domains=("casadellibro.com", "casadellibro.com.co"),
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
        key="panamericana",
        domains=("panamericana.com.co",),
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
    return f'"{record.isbn}"'


def build_retailer_search_queries(record: SourceBookRecord) -> list[str]:
    return [build_retailer_search_query(record)]


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
    cache: FetchResultCache | None = None,
    cache_ttl_seconds: float | None = None,
    max_retries: int = 2,
    backoff_seconds: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
    max_search_attempts_per_record: int | None = None,
    max_fetch_attempts_per_record: int | None = None,
) -> list[FetchResult]:
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        active_searcher = searcher or DuckDuckGoHtmlSearcher(timeout_seconds, client=client)
        active_page_fetcher = page_fetcher or _DefaultRetailerPageFetcher(
            timeout_seconds,
            client=client,
        )
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

            cached_entry = cache.get_entry(record.isbn) if cache is not None else None
            if cached_entry is not None:
                cached_result = cached_entry.result
                negative_cache_expired = (
                    cached_result.record is None
                    and cache_ttl_seconds is not None
                    and cache_ttl_seconds >= 0
                    and (time.time() - cached_entry.cached_at > cache_ttl_seconds)
                )
                if not negative_cache_expired and cached_result.record is not None:
                    augmented_results.append(
                        fetch_result.model_copy(
                            update={
                                "record": apply_retailer_editorial_record(
                                    record,
                                    cached_result.record,
                                )
                            }
                        )
                    )
                    continue
                if not negative_cache_expired:
                    augmented_results.append(
                        fetch_result.model_copy(
                            update={
                                "issue_codes": [
                                    *fetch_result.issue_codes,
                                    *(
                                        code
                                        for code in cached_result.issue_codes
                                        if code not in fetch_result.issue_codes
                                    ),
                                ]
                            }
                        )
                    )
                    continue

            retailer_issue_codes: list[str] = []
            retailer_record: SourceBookRecord | None = None
            search_attempts = 0
            fetch_attempts = 0

            if on_status_update is not None:
                on_status_update(
                    f"Retailer editorial lookup {index}/{len(fetch_results)}: {record.isbn}"
                )

            for profile in SUPPORTED_RETAILERS:
                candidate_urls: list[str] = []
                for query in build_retailer_search_queries(record):
                    if (
                        max_search_attempts_per_record is not None
                        and max_search_attempts_per_record >= 0
                        and search_attempts >= max_search_attempts_per_record
                    ):
                        retailer_issue_codes.extend(
                            code
                            for code in ["RETAILER_PAGE_SEARCH_BUDGET_EXHAUSTED"]
                            if code not in retailer_issue_codes
                        )
                        break

                    def _search_retailer_pages() -> list[str]:
                        return active_searcher.search(
                            query,
                            profile.domains,
                            limit=SEARCH_RESULT_LIMIT,
                        )

                    query_candidate_urls, search_issue_codes = _run_with_retry(
                        _search_retailer_pages,
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

                    search_attempts += 1

                    for candidate_url in query_candidate_urls:
                        if candidate_url not in candidate_urls:
                            candidate_urls.append(candidate_url)

                    if candidate_urls:
                        break

                if not candidate_urls:
                    continue

                for candidate_url in _rank_candidate_urls(candidate_urls, record):
                    if (
                        max_fetch_attempts_per_record is not None
                        and max_fetch_attempts_per_record >= 0
                        and fetch_attempts >= max_fetch_attempts_per_record
                    ):
                        retailer_issue_codes.extend(
                            code
                            for code in ["RETAILER_PAGE_FETCH_BUDGET_EXHAUSTED"]
                            if code not in retailer_issue_codes
                        )
                        break

                    if not _is_allowed_domain(candidate_url, profile.domains):
                        continue

                    fetch_attempts += 1
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
                failed_result = fetch_result.model_copy(
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
                if cache is not None:
                    cache.set(
                        failed_result.model_copy(update={"record": None}),
                        allow_empty=True,
                    )
                augmented_results.append(failed_result)
                continue

            if cache is not None:
                cache.set(
                    FetchResult(
                        isbn=record.isbn,
                        record=retailer_record,
                        errors=[],
                        issue_codes=[],
                    )
                )
            augmented_results.append(
                fetch_result.model_copy(
                    update={
                        "record": apply_retailer_editorial_record(record, retailer_record)
                    }
                )
            )

        return augmented_results


class _DefaultRetailerPageFetcher:
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
