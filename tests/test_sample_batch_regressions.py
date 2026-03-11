from pathlib import Path

import openpyxl

from book_store_assistant.config import AppConfig, ExecutionMode
from book_store_assistant.enrichment.models import GeneratedSynopsis
from book_store_assistant.pipeline.export import export_resolved_records
from book_store_assistant.pipeline.input import read_isbn_inputs
from book_store_assistant.pipeline.review_export import export_unresolved_results
from book_store_assistant.pipeline.service import process_isbn_file
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_1_PATH = PROJECT_ROOT / "data" / "input" / "sample_1.csv"
SAMPLE_2_PATH = PROJECT_ROOT / "data" / "input" / "sample_2.csv"


def _long_english_synopsis(isbn: str) -> str:
    return (
        f"This fixture description for {isbn} is intentionally long enough to provide "
        "grounded descriptive evidence for AI synopsis generation without inventing metadata."
    )


class FixtureSynopsisGenerator:
    def generate(self, isbn: str, evidence) -> GeneratedSynopsis | None:
        return GeneratedSynopsis(
            text=(
                f"Resumen generado para {isbn} a partir de evidencia suficiente y "
                "conservadora del registro de origen."
            ),
            evidence_indexes=[0],
        )


class FixtureBatchSource:
    def __init__(self, sample_name: str, fixture_isbns: list[str]) -> None:
        self.fixture_results = self._build_fixture_results(sample_name, fixture_isbns)

    def fetch(self, isbn: str) -> FetchResult:
        return self.fixture_results[isbn]

    def _build_fixture_results(
        self,
        sample_name: str,
        fixture_isbns: list[str],
    ) -> dict[str, FetchResult]:
        if sample_name == "sample_1":
            return _build_sample_1_fixture_results(fixture_isbns)

        return _build_sample_2_fixture_results(fixture_isbns)


def _build_fixture_record(
    isbn: str,
    *,
    synopsis: str | None,
    language: str | None,
    subject: str | None = "FICCION",
    categories: list[str] | None = None,
    author: str | None = "Fixture Author",
    editorial: str | None = "Fixture Editorial",
) -> SourceBookRecord:
    field_sources = {
        "title": "fixture_source",
        "author": "fixture_source",
        "editorial": "fixture_source",
    }
    if synopsis is not None:
        field_sources["synopsis"] = "fixture_source"
    if subject is not None:
        field_sources["subject"] = "fixture_source"
    if categories:
        field_sources["categories"] = "fixture_source"

    return SourceBookRecord(
        source_name="fixture_source",
        isbn=isbn,
        title=f"Fixture Title {isbn[-4:]}",
        author=author,
        editorial=editorial,
        synopsis=synopsis,
        subject=subject,
        categories=categories or [],
        language=language,
        field_sources=field_sources,
    )


def _build_fetch_error(isbn: str) -> FetchResult:
    return FetchResult(
        isbn=isbn,
        record=None,
        errors=["fixture_source: simulated fetch failure"],
        issue_codes=["FIXTURE_SOURCE:FIXTURE_FETCH_FAILURE"],
    )


def _build_sample_1_fixture_results(fixture_isbns: list[str]) -> dict[str, FetchResult]:
    english_synopsis_indexes = {0, 5, 9}
    fetch_error_indexes = {8}
    alias_subject_indexes = {3}
    results: dict[str, FetchResult] = {}

    for index, isbn in enumerate(fixture_isbns):
        if index in fetch_error_indexes:
            results[isbn] = _build_fetch_error(isbn)
            continue

        if index in english_synopsis_indexes:
            record = _build_fixture_record(
                isbn,
                synopsis=_long_english_synopsis(isbn),
                language="en",
            )
        elif index in alias_subject_indexes:
            record = _build_fixture_record(
                isbn,
                synopsis="Resumen existente del libro.",
                language="es",
                subject=None,
                categories=["Romance literature"],
            )
        else:
            record = _build_fixture_record(
                isbn,
                synopsis="Resumen existente del libro.",
                language="es",
            )

        results[isbn] = FetchResult(isbn=isbn, record=record, errors=[])

    return results


def _build_sample_2_fixture_results(fixture_isbns: list[str]) -> dict[str, FetchResult]:
    results: dict[str, FetchResult] = {}

    for index, isbn in enumerate(fixture_isbns):
        if index < 10:
            record = _build_fixture_record(
                isbn,
                synopsis="Resumen existente del libro.",
                language="es",
            )
        elif index < 20:
            record = _build_fixture_record(
                isbn,
                synopsis=_long_english_synopsis(isbn),
                language="en",
            )
        elif index < 25:
            results[isbn] = _build_fetch_error(isbn)
            continue
        elif index < 30:
            record = _build_fixture_record(
                isbn,
                synopsis="Resumen existente del libro.",
                language="es",
                subject=None,
                categories=[],
            )
        elif index < 35:
            record = _build_fixture_record(
                isbn,
                synopsis="Resumen existente del libro.",
                language="es",
                editorial=None,
            )
        elif index < 40:
            record = _build_fixture_record(
                isbn,
                synopsis="Resumen existente del libro.",
                language="es",
                author=None,
            )
        elif index < 45:
            record = _build_fixture_record(
                isbn,
                synopsis=None,
                language=None,
            )
        else:
            record = _build_fixture_record(
                isbn,
                synopsis="Resumen existente del libro.",
                language="es",
                subject=None,
                categories=["Romance literature"],
            )

        results[isbn] = FetchResult(isbn=isbn, record=record, errors=[])

    return results


def test_sample_1_batch_regression_in_ai_mode(tmp_path: Path) -> None:
    fixture_isbns = [item.isbn for item in read_isbn_inputs(SAMPLE_1_PATH).valid_inputs]
    result = process_isbn_file(
        SAMPLE_1_PATH,
        source=FixtureBatchSource("sample_1", fixture_isbns),
        config=AppConfig(execution_mode=ExecutionMode.AI_ENRICHED),
        generator=FixtureSynopsisGenerator(),
    )

    resolved_count = sum(1 for item in result.resolution_results if item.record is not None)
    unresolved_count = sum(1 for item in result.resolution_results if item.record is None)
    applied_count = sum(1 for item in result.enrichment_results if item.applied)

    assert len(result.input_result.valid_inputs) == 10
    assert sum(1 for item in result.fetch_results if item.record is not None) == 9
    assert resolved_count == 9
    assert unresolved_count == 1
    assert applied_count == 3

    resolved_output = tmp_path / "sample_1_books.xlsx"
    review_output = tmp_path / "sample_1_review.xlsx"
    export_resolved_records(result.resolution_results, resolved_output)
    export_unresolved_results(result.resolution_results, review_output)

    resolved_sheet = openpyxl.load_workbook(resolved_output).active
    review_sheet = openpyxl.load_workbook(review_output).active

    assert resolved_sheet.max_row == 10
    assert review_sheet.max_row == 2


def test_sample_2_batch_regression_in_ai_mode(tmp_path: Path) -> None:
    fixture_isbns = [item.isbn for item in read_isbn_inputs(SAMPLE_2_PATH).valid_inputs]
    result = process_isbn_file(
        SAMPLE_2_PATH,
        source=FixtureBatchSource("sample_2", fixture_isbns),
        config=AppConfig(execution_mode=ExecutionMode.AI_ENRICHED),
        generator=FixtureSynopsisGenerator(),
    )

    resolved_count = sum(1 for item in result.resolution_results if item.record is not None)
    unresolved_count = sum(1 for item in result.resolution_results if item.record is None)
    applied_count = sum(1 for item in result.enrichment_results if item.applied)

    assert len(result.input_result.valid_inputs) == 49
    assert result.input_result.invalid_values == ["9788449333830"]
    assert sum(1 for item in result.fetch_results if item.record is not None) == 44
    assert resolved_count == 24
    assert unresolved_count == 25
    assert applied_count == 10

    resolved_output = tmp_path / "sample_2_books.xlsx"
    review_output = tmp_path / "sample_2_review.xlsx"
    export_resolved_records(result.resolution_results, resolved_output)
    export_unresolved_results(result.resolution_results, review_output)

    resolved_sheet = openpyxl.load_workbook(resolved_output).active
    review_sheet = openpyxl.load_workbook(review_output).active

    assert resolved_sheet.max_row == 25
    assert review_sheet.max_row == 26
