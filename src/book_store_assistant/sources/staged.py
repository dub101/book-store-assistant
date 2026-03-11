import time
from collections.abc import Callable
from pathlib import Path

from book_store_assistant.config import AppConfig
from book_store_assistant.pipeline.contracts import ISBNInput
from book_store_assistant.sources.bne import BneSruSource
from book_store_assistant.sources.cache import FetchResultCache
from book_store_assistant.sources.google_books import GoogleBooksSource
from book_store_assistant.sources.intermediate import export_fetch_results, read_fetch_results
from book_store_assistant.sources.merge import merge_source_records
from book_store_assistant.sources.open_library import OpenLibrarySource
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.service import FetchCompleteCallback, FetchStartCallback

STAGED_SOURCE_CACHE_KEY = "staged_fetch_v1"
StageUpdateCallback = Callable[[str], None]


def _stage_output_path(intermediate_dir: Path, input_path: Path, stage_name: str) -> Path:
    return intermediate_dir / f"{input_path.stem}.{stage_name}.jsonl"


def _has_minimum_bibliographic_fields(result: FetchResult) -> bool:
    record = result.record
    return bool(
        record is not None
        and record.title
        and record.author
        and record.editorial
    )


def _has_subject_evidence(result: FetchResult) -> bool:
    record = result.record
    return bool(record is not None and (record.subject or record.categories))


def _is_fetch_complete_for_resolution(result: FetchResult) -> bool:
    return _has_minimum_bibliographic_fields(result) and _has_subject_evidence(result)


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


def _save_and_read_stage(results: list[FetchResult], path: Path) -> list[FetchResult]:
    export_fetch_results(results, path)
    return read_fetch_results(path)


def fetch_with_intermediate_stages(
    input_path: Path,
    inputs: list[ISBNInput],
    config: AppConfig,
    on_fetch_start: FetchStartCallback | None = None,
    on_fetch_complete: FetchCompleteCallback | None = None,
    on_stage_update: StageUpdateCallback | None = None,
) -> list[FetchResult]:
    cache = FetchResultCache(config.source_cache_dir, STAGED_SOURCE_CACHE_KEY)
    bne = BneSruSource(config)
    open_library = OpenLibrarySource(config)
    google_books = GoogleBooksSource(config)

    if on_stage_update is not None:
        on_stage_update(f"Stage: reading cache for {len(inputs)} ISBNs")

    cache_stage_results = [
        cache.get(item.isbn) or FetchResult(isbn=item.isbn, record=None, errors=[], issue_codes=[])
        for item in inputs
    ]
    cache_stage_results = _save_and_read_stage(
        cache_stage_results,
        _stage_output_path(config.intermediate_dir, input_path, "cache"),
    )

    merged_after_cache = {
        result.isbn: result
        for result in cache_stage_results
    }
    merged_after_bne = merged_after_cache
    if config.bne_lookup_enabled:
        bne_candidates = [
            item.isbn
            for item in inputs
            if not _is_fetch_complete_for_resolution(merged_after_cache[item.isbn])
        ]
        if on_stage_update is not None:
            on_stage_update(f"Stage: querying BNE for {len(bne_candidates)} ISBNs")

        bne_stage_results: list[FetchResult] = []
        for index, isbn in enumerate(bne_candidates):
            if on_stage_update is not None:
                on_stage_update(f"BNE {index + 1}/{len(bne_candidates)}: {isbn}")
            if index > 0 and config.source_request_pause_seconds > 0:
                time.sleep(config.source_request_pause_seconds)

            result = bne.fetch(isbn)
            bne_stage_results.append(result)
            cache.set(result)

        bne_stage_results = _save_and_read_stage(
            bne_stage_results,
            _stage_output_path(config.intermediate_dir, input_path, "bne"),
        )
        bne_by_isbn = {
            result.isbn: _prefix_result(result, bne.source_name)
            for result in bne_stage_results
        }

        merged_after_bne = {}
        for item in inputs:
            isbn = item.isbn
            merged_after_bne[isbn] = _merge_stage_results(
                merged_after_cache[isbn],
                bne_by_isbn.get(
                    isbn,
                    FetchResult(isbn=isbn, record=None, errors=[], issue_codes=[]),
                ),
            )

    open_library_candidates = [
        item.isbn
        for item in inputs
        if not _is_fetch_complete_for_resolution(merged_after_bne[item.isbn])
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
        for result in batch_results:
            cache.set(result)

    open_library_stage_results = _save_and_read_stage(
        open_library_stage_results,
        _stage_output_path(config.intermediate_dir, input_path, "open_library"),
    )
    open_library_by_isbn = {
        result.isbn: _prefix_result(result, open_library.source_name)
        for result in open_library_stage_results
    }

    merged_after_open_library: dict[str, FetchResult] = {}
    for item in inputs:
        isbn = item.isbn
        cache_result = merged_after_bne[isbn]
        open_library_result = open_library_by_isbn.get(
            isbn,
            FetchResult(isbn=isbn, record=None, errors=[], issue_codes=[]),
        )
        merged_after_open_library[isbn] = _merge_stage_results(cache_result, open_library_result)

    google_candidates = [
        item.isbn
        for item in inputs
        if not _is_fetch_complete_for_resolution(merged_after_open_library[item.isbn])
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
        cache.set(result)

    google_stage_results = _save_and_read_stage(
        google_stage_results,
        _stage_output_path(config.intermediate_dir, input_path, "google_books"),
    )
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
