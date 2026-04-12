import time
from collections.abc import Callable
from pathlib import Path

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


def fetch_with_stages(
    input_path: Path,
    inputs: list[ISBNInput],
    config: AppConfig,
    on_fetch_start: FetchStartCallback | None = None,
    on_fetch_complete: FetchCompleteCallback | None = None,
    on_stage_update: StageUpdateCallback | None = None,
) -> list[FetchResult]:
    del input_path
    isbndb = ISBNdbSource(config)
    open_library = OpenLibrarySource(config)
    google_books = GoogleBooksSource(config)

    if on_stage_update is not None:
        on_stage_update(f"Stage: initializing fetch for {len(inputs)} ISBNs")

    cache_stage_results = [
        FetchResult(isbn=item.isbn, record=None, errors=[], issue_codes=[])
        for item in inputs
    ]

    merged_after_cache = {
        result.isbn: result
        for result in cache_stage_results
    }

    merged_after_isbndb = merged_after_cache
    if config.isbndb_lookup_enabled and config.isbndb_api_key:
        isbndb_candidates = [
            item.isbn
            for item in inputs
            if _needs_additional_metadata(merged_after_cache.get(item.isbn))
        ]
        if on_stage_update is not None:
            on_stage_update(f"Stage: querying ISBNdb for {len(isbndb_candidates)} ISBNs")

        isbndb_stage_results: list[FetchResult] = []
        for index, isbn in enumerate(isbndb_candidates):
            if on_stage_update is not None:
                on_stage_update(f"ISBNdb {index + 1}/{len(isbndb_candidates)}: {isbn}")
            if index > 0 and config.source_request_pause_seconds > 0:
                time.sleep(config.source_request_pause_seconds)

            result = isbndb.fetch(isbn)
            isbndb_stage_results.append(result)
        isbndb_by_isbn = {
            result.isbn: _prefix_result(result, isbndb.source_name)
            for result in isbndb_stage_results
        }

        merged_after_isbndb = {}
        for item in inputs:
            isbn = item.isbn
            merged_after_isbndb[isbn] = _merge_stage_results(
                merged_after_cache[isbn],
                isbndb_by_isbn.get(
                    isbn,
                    FetchResult(isbn=isbn, record=None, errors=[], issue_codes=[]),
                ),
            )

    merged_after_national = merged_after_isbndb
    if config.national_agency_routing_enabled:
        national_candidates = [
            item.isbn
            for item in inputs
            if _needs_additional_metadata(merged_after_isbndb.get(item.isbn))
        ]
        if on_stage_update is not None:
            on_stage_update(
                f"Stage: querying national agencies for {len(national_candidates)} ISBNs"
            )

        national_stage_results: list[FetchResult] = []
        for index, isbn in enumerate(national_candidates):
            source = get_national_source(isbn, config)
            if source is None:
                continue
            if on_stage_update is not None:
                on_stage_update(
                    f"National ({source.source_name}) "
                    f"{index + 1}/{len(national_candidates)}: {isbn}"
                )
            if national_stage_results and config.source_request_pause_seconds > 0:
                time.sleep(config.source_request_pause_seconds)

            result = source.fetch(isbn)
            national_stage_results.append(
                _prefix_result(result, source.source_name)
            )
        national_by_isbn = {
            result.isbn: result for result in national_stage_results
        }

        merged_after_national = {}
        for item in inputs:
            isbn = item.isbn
            merged_after_national[isbn] = _merge_stage_results(
                merged_after_isbndb[isbn],
                national_by_isbn.get(
                    isbn,
                    FetchResult(isbn=isbn, record=None, errors=[], issue_codes=[]),
                ),
            )

    open_library_candidates = [
        item.isbn
        for item in inputs
        if _needs_additional_metadata(merged_after_national.get(item.isbn))
    ]
    if on_stage_update is not None:
        on_stage_update(
            "Stage: querying Open Library for "
            f"{len(open_library_candidates)} ISBNs "
            f"in {len(_chunked(open_library_candidates, config.open_library_batch_size))} batch(es)"
        )

    open_library_stage_results: list[FetchResult] = []
    for index, batch in enumerate(
        _chunked(open_library_candidates, config.open_library_batch_size)
    ):
        if on_stage_update is not None and batch:
            on_stage_update(
                f"Open Library batch {index + 1}: {len(batch)} ISBNs"
            )
        if index > 0 and config.source_request_pause_seconds > 0:
            time.sleep(config.source_request_pause_seconds)

        batch_results = open_library.fetch_batch(batch)
        open_library_stage_results.extend(batch_results)
    open_library_by_isbn = {
        result.isbn: _prefix_result(result, open_library.source_name)
        for result in open_library_stage_results
    }

    merged_after_open_library: dict[str, FetchResult] = {}
    for item in inputs:
        isbn = item.isbn
        cache_result = merged_after_national[isbn]
        open_library_result = open_library_by_isbn.get(
            isbn,
            FetchResult(isbn=isbn, record=None, errors=[], issue_codes=[]),
        )
        merged_after_open_library[isbn] = _merge_stage_results(cache_result, open_library_result)

    google_candidates = [
        item.isbn
        for item in inputs
        if _needs_additional_metadata(merged_after_open_library.get(item.isbn))
    ]
    if on_stage_update is not None:
        on_stage_update(f"Stage: querying Google Books for {len(google_candidates)} ISBNs")

    google_stage_results: list[FetchResult] = []
    for index, isbn in enumerate(google_candidates):
        if on_stage_update is not None:
            on_stage_update(
                f"Google Books {index + 1}/{len(google_candidates)}: {isbn}"
            )
        if index > 0 and config.source_request_pause_seconds > 0:
            time.sleep(config.source_request_pause_seconds)

        result = google_books.fetch(isbn)
        google_stage_results.append(result)
    google_by_isbn = {
        result.isbn: _prefix_result(result, google_books.source_name)
        for result in google_stage_results
    }

    final_results: list[FetchResult] = []
    total = len(inputs)
    if on_stage_update is not None:
        on_stage_update("Stage: merging staged fetch results")
    for index, item in enumerate(inputs, start=1):
        if on_fetch_start is not None:
            on_fetch_start(index, total, item.isbn)

        result = _merge_stage_results(
            merged_after_open_library[item.isbn],
            google_by_isbn.get(
                item.isbn,
                FetchResult(isbn=item.isbn, record=None, errors=[], issue_codes=[]),
            ),
        )
        final_results.append(result)

        if on_fetch_complete is not None:
            on_fetch_complete(index, total, result)

    return final_results
