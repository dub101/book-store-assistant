import time
from collections.abc import Callable, Iterable
from typing import Any

from book_store_assistant.sources.models import SourceBookRecord

SearchQueryBuilder = Callable[[SourceBookRecord, Any], list[str]]
DirectUrlBuilder = Callable[[SourceBookRecord, Any], list[str]]
RecordExtractor = Callable[[str, str, str, Any], SourceBookRecord | None]
CandidateRanker = Callable[[list[str], SourceBookRecord], list[str]]
SearchOperation = Callable[[str, tuple[str, ...], int], list[str]]
FetchOperation = Callable[[str], str | None]
PageValidator = Callable[[str, str, SourceBookRecord, Any], tuple[bool, list[str]]]
RetryRunner = Callable[
    [Callable[[], Any], str, int, float, Callable[[float], None]],
    tuple[Any | None, list[str]],
]
AllowedDomainChecker = Callable[[str, tuple[str, ...]], bool]


def lookup_exact_page_record(
    record: SourceBookRecord,
    profiles: Iterable[Any],
    search_queries: SearchQueryBuilder,
    direct_query_urls: DirectUrlBuilder,
    extract_record: RecordExtractor,
    search: SearchOperation,
    fetch_text: FetchOperation,
    run_with_retry: RetryRunner,
    rank_candidate_urls: CandidateRanker,
    is_allowed_domain: AllowedDomainChecker,
    search_issue_source: str,
    fetch_issue_source: str,
    page_validator: PageValidator | None = None,
    search_result_limit: int = 3,
    max_retries: int = 0,
    backoff_seconds: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
    max_search_attempts_per_record: int | None = None,
    max_fetch_attempts_per_record: int | None = None,
) -> tuple[SourceBookRecord | None, list[str]]:
    issue_codes: list[str] = []
    search_attempts = 0
    fetch_attempts = 0

    for profile in profiles:
        candidate_urls: list[str] = []

        for direct_url in direct_query_urls(record, profile):
            if (
                max_fetch_attempts_per_record is not None
                and max_fetch_attempts_per_record >= 0
                and fetch_attempts >= max_fetch_attempts_per_record
            ):
                if "PAGE_FETCH_BUDGET_EXHAUSTED" not in issue_codes:
                    issue_codes.append("PAGE_FETCH_BUDGET_EXHAUSTED")
                return None, issue_codes

            fetch_attempts += 1
            def _fetch_direct_url() -> str | None:
                return fetch_text(direct_url)

            page_html, fetch_issue_codes = run_with_retry(
                _fetch_direct_url,
                fetch_issue_source,
                max_retries,
                backoff_seconds,
                sleep,
            )
            if page_html is None:
                for code in fetch_issue_codes:
                    if code not in issue_codes:
                        issue_codes.append(code)
                continue

            if page_validator is not None:
                is_valid, validation_issue_codes = page_validator(
                    page_html,
                    direct_url,
                    record,
                    profile,
                )
                for code in validation_issue_codes:
                    if code not in issue_codes:
                        issue_codes.append(code)
                if not is_valid:
                    continue

            extracted = extract_record(page_html, direct_url, record.isbn, profile)
            if extracted is not None:
                return extracted, issue_codes

        for query in search_queries(record, profile):
            if (
                max_search_attempts_per_record is not None
                and max_search_attempts_per_record >= 0
                and search_attempts >= max_search_attempts_per_record
            ):
                if "PAGE_SEARCH_BUDGET_EXHAUSTED" not in issue_codes:
                    issue_codes.append("PAGE_SEARCH_BUDGET_EXHAUSTED")
                break

            def _search_query() -> list[str]:
                return search(query, profile.domains, search_result_limit)

            query_candidate_urls, search_issue_codes = run_with_retry(
                _search_query,
                search_issue_source,
                max_retries,
                backoff_seconds,
                sleep,
            )
            if query_candidate_urls is None:
                for code in search_issue_codes:
                    if code not in issue_codes:
                        issue_codes.append(code)
                continue

            search_attempts += 1
            for candidate_url in query_candidate_urls:
                if candidate_url not in candidate_urls:
                    candidate_urls.append(candidate_url)

            if candidate_urls:
                break

        for candidate_url in rank_candidate_urls(candidate_urls, record):
            if (
                max_fetch_attempts_per_record is not None
                and max_fetch_attempts_per_record >= 0
                and fetch_attempts >= max_fetch_attempts_per_record
            ):
                if "PAGE_FETCH_BUDGET_EXHAUSTED" not in issue_codes:
                    issue_codes.append("PAGE_FETCH_BUDGET_EXHAUSTED")
                return None, issue_codes

            if not is_allowed_domain(candidate_url, profile.domains):
                continue

            fetch_attempts += 1
            def _fetch_candidate_url() -> str | None:
                return fetch_text(candidate_url)

            page_html, fetch_issue_codes = run_with_retry(
                _fetch_candidate_url,
                fetch_issue_source,
                max_retries,
                backoff_seconds,
                sleep,
            )
            if page_html is None:
                for code in fetch_issue_codes:
                    if code not in issue_codes:
                        issue_codes.append(code)
                continue

            if page_validator is not None:
                is_valid, validation_issue_codes = page_validator(
                    page_html,
                    candidate_url,
                    record,
                    profile,
                )
                for code in validation_issue_codes:
                    if code not in issue_codes:
                        issue_codes.append(code)
                if not is_valid:
                    continue

            extracted = extract_record(page_html, candidate_url, record.isbn, profile)
            if extracted is not None:
                return extracted, issue_codes

    return None, issue_codes
