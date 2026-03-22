import time
from collections.abc import Callable
from urllib.parse import urlparse

import httpx

from book_store_assistant.sources.issues import classify_http_issue, no_match_issue_code
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.publisher_pages import (
    SUPPORTED_PUBLISHERS,
    DuckDuckGoHtmlSearcher,
    PublisherPageSearcher,
    PublisherProfile,
    _is_allowed_domain,
    _publisher_lookup_issue_code,
    _publisher_page_validator,
    _rank_candidate_urls,
    _retry_delay_seconds,
    _should_retry_http_error,
    apply_publisher_page_record,
    extract_publisher_page_record,
)
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.search_queries import (
    append_query,
    clean_query_text,
    editorial_query_terms,
)

PublisherDiscoveryStatusCallback = Callable[[str], None]


def _needs_publisher_discovery(record: SourceBookRecord) -> bool:
    return not record.title or not record.author or not record.editorial


def _run_with_retry(
    operation: Callable[[], str | list[str] | None],
    source_name: str,
    max_retries: int,
    backoff_seconds: float,
    sleep: Callable[[float], None],
) -> tuple[str | list[str] | None, list[str]]:
    issue_codes: list[str] = []

    for attempt in range(max_retries + 1):
        try:
            return operation(), issue_codes
        except httpx.HTTPError as exc:
            for code in classify_http_issue(source_name, exc):
                if code not in issue_codes:
                    issue_codes.append(code)
            if not _should_retry_http_error(exc, attempt, max_retries):
                return None, issue_codes
            sleep(_retry_delay_seconds(attempt, backoff_seconds, exc))

    return None, issue_codes


def _all_publisher_domains() -> tuple[str, ...]:
    seen: set[str] = set()
    domains: list[str] = []
    for profile in SUPPORTED_PUBLISHERS:
        for domain in profile.domains:
            normalized = domain.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            domains.append(normalized)
    return tuple(domains)


def _publisher_search_domain_groups() -> list[tuple[str, ...]]:
    groups: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for profile in SUPPORTED_PUBLISHERS:
        domains = tuple(domain.casefold() for domain in profile.domains)
        if not domains or domains in seen:
            continue
        seen.add(domains)
        groups.append(domains)
    all_domains = _all_publisher_domains()
    if all_domains and all_domains not in seen:
        groups.append(all_domains)
    return groups


def _profile_for_url(url: str) -> PublisherProfile | None:
    hostname = urlparse(url).hostname
    if hostname is None:
        return None

    normalized_hostname = hostname.casefold()
    for profile in SUPPORTED_PUBLISHERS:
        if any(
            normalized_hostname == domain.casefold()
            or normalized_hostname.endswith(f".{domain.casefold()}")
            for domain in profile.domains
        ):
            return profile

    return None


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


def build_publisher_discovery_search_queries(record: SourceBookRecord) -> list[str]:
    title = clean_query_text(record.title)
    author = clean_query_text(record.author)
    editorial_terms = editorial_query_terms(record.editorial)

    queries: list[str] = []
    append_query(queries, record.isbn, title, author)
    if not queries and editorial_terms:
        append_query(queries, record.isbn, title, editorial_terms[0])
    if not queries:
        append_query(queries, record.isbn, title)
    if not queries and editorial_terms:
        append_query(queries, record.isbn, author, editorial_terms[0])
    if not queries:
        append_query(queries, record.isbn, author)
    if not queries and editorial_terms:
        append_query(queries, record.isbn, editorial_terms[0])
    append_query(queries, record.isbn)
    return queries


def _apply_publisher_discovery_record(
    existing_record: SourceBookRecord,
    publisher_record: SourceBookRecord,
) -> SourceBookRecord:
    return apply_publisher_page_record(existing_record, publisher_record)


class _DefaultPageFetcher:
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


def augment_fetch_results_with_publisher_discovery(
    fetch_results: list[FetchResult],
    timeout_seconds: float,
    searcher: PublisherPageSearcher | None = None,
    page_fetcher: _DefaultPageFetcher | None = None,
    on_status_update: PublisherDiscoveryStatusCallback | None = None,
    max_retries: int = 2,
    backoff_seconds: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
    max_search_attempts_per_record: int | None = None,
    max_fetch_attempts_per_record: int | None = None,
    search_result_limit: int = 5,
    force_lookup_isbns: set[str] | None = None,
) -> list[FetchResult]:
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        active_searcher = searcher or DuckDuckGoHtmlSearcher(timeout_seconds, client=client)
        active_page_fetcher = page_fetcher or _DefaultPageFetcher(timeout_seconds, client=client)
        augmented_results: list[FetchResult] = []
        publisher_domains = _all_publisher_domains()
        search_domain_groups = _publisher_search_domain_groups()

        if on_status_update is not None:
            on_status_update(
                "Stage: discovering exact-ISBN publisher pages "
                f"for {len(fetch_results)} fetched records"
            )

        for index, fetch_result in enumerate(fetch_results, start=1):
            record = fetch_result.record
            if record is None:
                augmented_results.append(fetch_result)
                continue

            force_lookup = force_lookup_isbns is not None and record.isbn in force_lookup_isbns
            if not force_lookup and not _needs_publisher_discovery(record):
                augmented_results.append(fetch_result)
                continue

            if on_status_update is not None:
                on_status_update(
                    f"Publisher discovery {index}/{len(fetch_results)}: {record.isbn}"
                )

            search_attempts = 0
            fetch_attempts = 0
            candidate_urls: list[str] = []
            search_issue_codes: list[str] = []
            queries = build_publisher_discovery_search_queries(record)
            for allowed_domains in search_domain_groups:
                for query in queries:
                    if (
                        max_search_attempts_per_record is not None
                        and max_search_attempts_per_record >= 0
                        and search_attempts >= max_search_attempts_per_record
                    ):
                        break

                    def _search_query() -> list[str]:
                        return active_searcher.search(query, allowed_domains, search_result_limit)

                    result_urls, issue_codes = _run_with_retry(
                        _search_query,
                        "publisher_page_search",
                        max_retries,
                        backoff_seconds,
                        sleep,
                    )
                    search_attempts += 1
                    search_issue_codes = _merge_issue_codes(search_issue_codes, issue_codes)
                    if result_urls is None:
                        continue
                    for url in result_urls:
                        if url not in candidate_urls:
                            candidate_urls.append(url)
                    if candidate_urls:
                        break
                if candidate_urls or (
                    max_search_attempts_per_record is not None
                    and max_search_attempts_per_record >= 0
                    and search_attempts >= max_search_attempts_per_record
                ):
                    break

            discovered_record: SourceBookRecord | None = None
            discovered_issue_codes = list(search_issue_codes)
            for candidate_url in _rank_candidate_urls(candidate_urls, record):
                if (
                    max_fetch_attempts_per_record is not None
                    and max_fetch_attempts_per_record >= 0
                    and fetch_attempts >= max_fetch_attempts_per_record
                ):
                    break
                if not _is_allowed_domain(candidate_url, publisher_domains):
                    continue
                profile = _profile_for_url(candidate_url)
                if profile is None:
                    continue

                def _fetch_candidate_url() -> str | None:
                    return active_page_fetcher.fetch_text(candidate_url)

                page_html, issue_codes = _run_with_retry(
                    _fetch_candidate_url,
                    "publisher_page_fetch",
                    max_retries,
                    backoff_seconds,
                    sleep,
                )
                fetch_attempts += 1
                discovered_issue_codes = _merge_issue_codes(discovered_issue_codes, issue_codes)
                if page_html is None or not isinstance(page_html, str):
                    continue

                is_valid, validation_issue_codes = _publisher_page_validator(
                    page_html,
                    candidate_url,
                    record,
                    profile,
                )
                discovered_issue_codes = _merge_issue_codes(
                    discovered_issue_codes,
                    validation_issue_codes,
                )
                if not is_valid:
                    continue

                extracted = extract_publisher_page_record(
                    page_html,
                    candidate_url,
                    record.isbn,
                    profile,
                )
                if extracted is not None:
                    discovered_record = extracted
                    break

            if discovered_record is None:
                failed_result = fetch_result.model_copy(
                    update={
                        "issue_codes": _merge_issue_codes(
                            fetch_result.issue_codes,
                            [
                                _publisher_lookup_issue_code(code)
                                for code in discovered_issue_codes
                            ],
                            [no_match_issue_code("publisher_page")],
                        )
                    }
                )
                augmented_results.append(failed_result)
                continue

            augmented_results.append(
                fetch_result.model_copy(
                    update={
                        "record": _apply_publisher_discovery_record(record, discovered_record)
                    }
                )
            )

        return augmented_results
