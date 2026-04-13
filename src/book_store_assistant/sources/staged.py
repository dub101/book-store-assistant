import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Protocol

from book_store_assistant.config import AppConfig
from book_store_assistant.pipeline.contracts import ISBNInput
from book_store_assistant.sources.google_books import GoogleBooksSource
from book_store_assistant.sources.isbn_routing import get_national_source
from book_store_assistant.sources.isbndb import ISBNdbSource
from book_store_assistant.sources.merge import merge_source_records
from book_store_assistant.sources.open_library import OpenLibrarySource
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.service import FetchCompleteCallback, FetchStartCallback

StageUpdateCallback = Callable[[str], None]

MAX_CONCURRENT_REQUESTS = 3


class ISBNFetcher(Protocol):
    source_name: str

    def fetch(self, isbn: str) -> FetchResult: ...


def _prefix_result(result: FetchResult, source_name: str) -> FetchResult:
    prefixed_errors = [f"{source_name}: {error}" for error in result.errors]
    prefixed_issue_codes = [
        f"{source_name.upper()}:{issue_code}" for issue_code in result.issue_codes
    ]
    return result.model_copy(
        update={"errors": prefixed_errors, "issue_codes": prefixed_issue_codes}
    )


def _merge_stage_results(*results: FetchResult) -> FetchResult:
    successful_records = [result.record for result in results if result.record is not None]
    merged_errors: list[str] = []
    merged_issue_codes: list[str] = []
    seen_errors: set[str] = set()
    seen_issue_codes: set[str] = set()

    for result in results:
        for error in result.errors:
            if error in seen_errors:
                continue
            seen_errors.add(error)
            merged_errors.append(error)

        for issue_code in result.issue_codes:
            if issue_code in seen_issue_codes:
                continue
            seen_issue_codes.add(issue_code)
            merged_issue_codes.append(issue_code)

    if successful_records:
        return FetchResult(
            isbn=results[0].isbn,
            record=merge_source_records(
                [record for record in successful_records if record is not None]
            ),
            errors=merged_errors,
            issue_codes=merged_issue_codes,
        )

    return FetchResult(
        isbn=results[0].isbn,
        record=None,
        errors=merged_errors,
        issue_codes=merged_issue_codes,
    )


def _chunked(values: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        return [values]

    return [values[index : index + size] for index in range(0, len(values), size)]


def _has_text(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _needs_additional_metadata(result: FetchResult | None) -> bool:
    if result is None or result.record is None:
        return True

    record = result.record
    return not (
        _has_text(record.title)
        and _has_text(record.author)
        and _has_text(record.editorial)
    )


@dataclass
class _StageResult:
    isbn: str
    result: FetchResult


def _fetch_one(
    isbn: str,
    source: ISBNFetcher,
    pause_seconds: float,
    rate_limiter: list[float],
) -> _StageResult:
    now = time.monotonic()
    if rate_limiter:
        elapsed = now - rate_limiter[0]
        if elapsed < pause_seconds:
            time.sleep(pause_seconds - elapsed)
    rate_limiter.clear()
    rate_limiter.append(time.monotonic())
    result = source.fetch(isbn)
    return _StageResult(isbn=isbn, result=_prefix_result(result, source.source_name))


def _run_stage_concurrent(
    candidates: list[str],
    source: ISBNFetcher,
    pause_seconds: float,
    on_status_update: StageUpdateCallback | None,
    stage_label: str,
) -> dict[str, FetchResult]:
    if not candidates:
        return {}

    rate_limiter: list[float] = []
    results: dict[str, FetchResult] = {}

    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = {}
        for index, isbn in enumerate(candidates):
            if on_status_update is not None:
                on_status_update(f"{stage_label} {index + 1}/{len(candidates)}: {isbn}")
            future = executor.submit(
                _fetch_one, isbn, source, pause_seconds, rate_limiter
            )
            futures[future] = isbn

        for future in as_completed(futures):
            stage_result = future.result()
            results[stage_result.isbn] = stage_result.result

    return results


def _merge_stage_into(
    inputs: list[ISBNInput],
    current: dict[str, FetchResult],
    stage_results: dict[str, FetchResult],
) -> dict[str, FetchResult]:
    merged: dict[str, FetchResult] = {}
    for item in inputs:
        isbn = item.isbn
        merged[isbn] = _merge_stage_results(
            current[isbn],
            stage_results.get(
                isbn,
                FetchResult(isbn=isbn, record=None, errors=[], issue_codes=[]),
            ),
        )
    return merged


def fetch_with_stages(
    inputs: list[ISBNInput],
    config: AppConfig,
    on_fetch_start: FetchStartCallback | None = None,
    on_fetch_complete: FetchCompleteCallback | None = None,
    on_stage_update: StageUpdateCallback | None = None,
) -> list[FetchResult]:
    if on_stage_update is not None:
        on_stage_update(f"Stage: initializing fetch for {len(inputs)} ISBNs")

    current = {
        item.isbn: FetchResult(isbn=item.isbn, record=None, errors=[], issue_codes=[])
        for item in inputs
    }
    pause = config.source_request_pause_seconds

    # --- Stage 1: ISBNdb ---
    if config.isbndb_lookup_enabled and config.isbndb_api_key:
        isbndb = ISBNdbSource(config)
        candidates = [i.isbn for i in inputs if _needs_additional_metadata(current.get(i.isbn))]
        if on_stage_update is not None:
            on_stage_update(f"Stage: querying ISBNdb for {len(candidates)} ISBNs")
        stage_results = _run_stage_concurrent(
            candidates, isbndb, isbndb.adaptive_pause, on_stage_update, "ISBNdb"
        )
        current = _merge_stage_into(inputs, current, stage_results)

    # --- Stage 2: National agencies ---
    if config.national_agency_routing_enabled:
        national_candidates = [
            i.isbn for i in inputs if _needs_additional_metadata(current.get(i.isbn))
        ]
        if on_stage_update is not None:
            on_stage_update(
                f"Stage: querying national agencies for {len(national_candidates)} ISBNs"
            )
        national_results: dict[str, FetchResult] = {}
        for index, isbn in enumerate(national_candidates):
            source = get_national_source(isbn, config)
            if source is None:
                continue
            if on_stage_update is not None:
                on_stage_update(
                    f"National ({source.source_name}) "
                    f"{index + 1}/{len(national_candidates)}: {isbn}"
                )
            if national_results and pause > 0:
                time.sleep(pause)
            result = source.fetch(isbn)
            national_results[isbn] = _prefix_result(result, source.source_name)
        current = _merge_stage_into(inputs, current, national_results)

    # --- Stage 3: Open Library (batch) ---
    ol_candidates = [i.isbn for i in inputs if _needs_additional_metadata(current.get(i.isbn))]
    if on_stage_update is not None:
        batches = _chunked(ol_candidates, config.open_library_batch_size)
        on_stage_update(
            f"Stage: querying Open Library for {len(ol_candidates)} ISBNs "
            f"in {len(batches)} batch(es)"
        )
    open_library = OpenLibrarySource(config)
    ol_results_list: list[FetchResult] = []
    for index, batch in enumerate(_chunked(ol_candidates, config.open_library_batch_size)):
        if on_stage_update is not None and batch:
            on_stage_update(f"Open Library batch {index + 1}: {len(batch)} ISBNs")
        if index > 0 and pause > 0:
            time.sleep(pause)
        ol_results_list.extend(open_library.fetch_batch(batch))
    ol_by_isbn = {
        r.isbn: _prefix_result(r, open_library.source_name) for r in ol_results_list
    }
    current = _merge_stage_into(inputs, current, ol_by_isbn)

    # --- Stage 4: Google Books ---
    google_candidates = [
        i.isbn for i in inputs if _needs_additional_metadata(current.get(i.isbn))
    ]
    if on_stage_update is not None:
        on_stage_update(f"Stage: querying Google Books for {len(google_candidates)} ISBNs")
    google_books = GoogleBooksSource(config)
    google_results = _run_stage_concurrent(
        google_candidates, google_books, pause, on_stage_update, "Google Books"
    )
    current = _merge_stage_into(inputs, current, google_results)

    # --- Final merge and callbacks ---
    final_results: list[FetchResult] = []
    total = len(inputs)
    if on_stage_update is not None:
        on_stage_update("Stage: merging staged fetch results")
    for index, item in enumerate(inputs, start=1):
        if on_fetch_start is not None:
            on_fetch_start(index, total, item.isbn)
        final_results.append(current[item.isbn])
        if on_fetch_complete is not None:
            on_fetch_complete(index, total, current[item.isbn])

    return final_results
