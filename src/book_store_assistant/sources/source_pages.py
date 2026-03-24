import json
import re
import time
from collections.abc import Callable
from html import unescape
from urllib.parse import urlparse

import httpx

from book_store_assistant.sources.diagnostics import changed_record_fields, with_diagnostic
from book_store_assistant.sources.merge import merge_source_records
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.publisher_pages import (
    _clean_text,
    _coerce_http_url,
    _run_with_retry,
)
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.search_backend import DEFAULT_BROWSER_HEADERS, PageContentFetcher

SourcePageStatusCallback = Callable[[str], None]

GOOGLE_BOOKS_TITLE_SUFFIX = " - Google Libros"
GOOGLE_BOOKS_SOURCE_NAME = "source_page:google_books"
GOOGLE_BOOKS_TITLE_PATTERN = re.compile(
    r"<title>(?P<title>.*?)\s*-\s*(?P<author>.*?)\s*-\s*Google Libros</title>",
    re.IGNORECASE | re.DOTALL,
)
GOOGLE_BOOKS_INFO_PATTERN = re.compile(
    r'<div class="bookinfo_sectionwrap">.*?<div>.*?</div>\s*<div>\s*'
    r'<span[^>]*dir(?:=["\']?ltr["\']?)?[^>]*>(?P<editorial>[^<]+)</span>\s*,\s*'
    r'(?P<year>\d{4})\s*-',
    re.IGNORECASE | re.DOTALL,
)


def _is_google_books_url(url: str | None) -> bool:
    if url is None:
        return False

    hostname = (urlparse(url).hostname or "").casefold()
    return hostname.startswith("books.google.") or ".books.google." in hostname


def _needs_source_page_enrichment(fetch_result: FetchResult) -> bool:
    record = fetch_result.record
    if record is None or record.source_url is None:
        return False

    if not _is_google_books_url(str(record.source_url)):
        return False

    return not (
        bool((record.title or "").strip())
        and bool((record.author or "").strip())
        and bool((record.editorial or "").strip())
    )


def _parse_google_books_title_parts(html: str) -> tuple[str | None, str | None]:
    match = GOOGLE_BOOKS_TITLE_PATTERN.search(html)
    if match is None:
        return None, None

    return (
        _clean_text(unescape(match.group("title"))),
        _clean_text(unescape(match.group("author"))),
    )


def _extract_google_books_editorial(html: str) -> str | None:
    match = GOOGLE_BOOKS_INFO_PATTERN.search(html)
    if match is None:
        return None

    return _clean_text(unescape(match.group("editorial")))


def _build_google_books_page_record(
    record: SourceBookRecord,
    html: str,
    page_url: str,
) -> SourceBookRecord | None:
    title_match = GOOGLE_BOOKS_TITLE_PATTERN.search(html)
    title, author = _parse_google_books_title_parts(html)
    editorial = _extract_google_books_editorial(html)
    if not any((title, author, editorial)):
        return None

    source_url = _coerce_http_url(page_url)
    raw_source_payload = json.dumps(
        {
            "page_title": (
                _clean_text(unescape(title_match.group(0))) if title_match is not None else None
            ),
            "editorial": editorial,
        },
        ensure_ascii=False,
    )
    field_sources: dict[str, str] = {}
    field_confidence: dict[str, float] = {}

    if title:
        field_sources["title"] = GOOGLE_BOOKS_SOURCE_NAME
        field_confidence["title"] = 0.95
    if editorial:
        field_sources["editorial"] = GOOGLE_BOOKS_SOURCE_NAME
        field_confidence["editorial"] = 0.96
    if author and not record.author:
        field_sources["author"] = GOOGLE_BOOKS_SOURCE_NAME
        field_confidence["author"] = 0.8
    if source_url is not None:
        field_sources["source_url"] = GOOGLE_BOOKS_SOURCE_NAME
        field_confidence["source_url"] = 0.95

    return SourceBookRecord(
        source_name=GOOGLE_BOOKS_SOURCE_NAME,
        isbn=record.isbn,
        source_url=source_url,
        raw_source_payload=raw_source_payload,
        title=title,
        author=author if not record.author else None,
        editorial=editorial,
        field_sources=field_sources,
        field_confidence=field_confidence,
    )


def _apply_source_page_record(
    record: SourceBookRecord,
    extracted_record: SourceBookRecord,
) -> SourceBookRecord:
    merged_record = merge_source_records([record, extracted_record])
    field_sources = dict(merged_record.field_sources)
    field_confidence = dict(merged_record.field_confidence)
    updates: dict[str, object] = {}
    title_source = record.field_sources.get("title", record.source_name).casefold()

    if (
        extracted_record.title
        and extracted_record.title != record.title
        and "google_books" in title_source
    ):
        updates["title"] = extracted_record.title
        field_sources["title"] = extracted_record.field_sources["title"]
        field_confidence["title"] = extracted_record.field_confidence["title"]

    if not updates:
        return merged_record

    updates["field_sources"] = field_sources
    updates["field_confidence"] = field_confidence
    return merged_record.model_copy(update=updates)


def _extract_source_page_record(
    record: SourceBookRecord,
    html: str,
    page_url: str,
) -> SourceBookRecord | None:
    if _is_google_books_url(page_url):
        return _build_google_books_page_record(record, html, page_url)
    return None


class _DefaultSourcePageFetcher(PageContentFetcher):
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


def augment_fetch_results_with_source_pages(
    fetch_results: list[FetchResult],
    timeout_seconds: float,
    page_fetcher: PageContentFetcher | None = None,
    on_status_update: SourcePageStatusCallback | None = None,
    max_retries: int = 1,
    backoff_seconds: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> list[FetchResult]:
    targeted_results = [
        result for result in fetch_results if _needs_source_page_enrichment(result)
    ]
    if not targeted_results:
        return fetch_results

    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        active_page_fetcher = page_fetcher or _DefaultSourcePageFetcher(
            timeout_seconds,
            client=client,
        )
        augmented_results: list[FetchResult] = []
        targeted_index = 0

        if on_status_update is not None:
            on_status_update(
                "Stage: enriching "
                f"{len(targeted_results)} records from existing source pages"
            )

        for fetch_result in fetch_results:
            if not _needs_source_page_enrichment(fetch_result):
                augmented_results.append(fetch_result)
                continue

            targeted_index += 1
            record = fetch_result.record
            assert record is not None
            assert record.source_url is not None
            page_url = str(record.source_url)

            if on_status_update is not None:
                on_status_update(
                    f"Source page {targeted_index}/{len(targeted_results)}: {record.isbn}"
                )

            page_html, issue_codes = _run_with_retry(
                lambda: active_page_fetcher.fetch_text(page_url),
                "source_page_fetch",
                max_retries,
                backoff_seconds,
                sleep,
            )
            if page_html is None:
                augmented_results.append(
                    with_diagnostic(
                        fetch_result,
                        "source_pages",
                        "completed",
                        source_page_match=False,
                        source_page_url=page_url,
                        fetch_attempts=1,
                        issue_codes=issue_codes,
                    ).model_copy(
                        update={"issue_codes": [*fetch_result.issue_codes, *issue_codes]}
                    )
                )
                continue

            extracted_record = _extract_source_page_record(record, page_html, page_url)
            if extracted_record is None:
                augmented_results.append(
                    with_diagnostic(
                        fetch_result,
                        "source_pages",
                        "completed",
                        source_page_match=False,
                        source_page_url=page_url,
                        fetch_attempts=1,
                        issue_codes=issue_codes,
                    ).model_copy(
                        update={"issue_codes": [*fetch_result.issue_codes, *issue_codes]}
                    )
                )
                continue

            merged_record = _apply_source_page_record(record, extracted_record)
            changed_fields = changed_record_fields(record, merged_record)
            augmented_results.append(
                with_diagnostic(
                    fetch_result,
                    "source_pages",
                    "completed",
                    source_page_match=bool(changed_fields),
                    source_page_url=page_url,
                    fetch_attempts=1,
                    changed_fields=changed_fields,
                    issue_codes=issue_codes,
                ).model_copy(
                    update={
                        "record": merged_record,
                        "issue_codes": [*fetch_result.issue_codes, *issue_codes],
                    }
                )
            )

        return augmented_results
