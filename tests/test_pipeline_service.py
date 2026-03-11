from pathlib import Path
from unittest.mock import patch

from book_store_assistant.config import AppConfig, ExecutionMode
from book_store_assistant.enrichment.models import EnrichmentResult, GeneratedSynopsis
from book_store_assistant.models import BookRecord
from book_store_assistant.pipeline.service import (
    _attach_enrichment_results,
    _select_best_resolution_results,
    build_default_source,
    process_isbn_file,
)
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.defaults import build_default_sources
from book_store_assistant.sources.fallback import FallbackMetadataSource
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


class DummySource:
    def fetch(self, isbn: str) -> FetchResult:
        return FetchResult(isbn=isbn, record=None, errors=["No match"])


def test_build_default_sources_returns_sources_in_precedence_order() -> None:
    sources = build_default_sources()

    assert len(sources) == 2
    assert sources[0].source_name == "google_books"
    assert sources[1].source_name == "open_library"


def test_build_default_source_returns_fallback_metadata_source() -> None:
    source = build_default_source()

    assert isinstance(source, FallbackMetadataSource)
    assert len(source.sources) == 2
    assert source.sources[0].source_name == "google_books"
    assert source.sources[1].source_name == "open_library"


def test_process_isbn_file_uses_injected_source(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\ninvalid\n", encoding="utf-8")

    result = process_isbn_file(input_file, source=DummySource())

    assert len(result.input_result.valid_inputs) == 1
    assert result.input_result.invalid_values == ["invalid"]
    assert len(result.fetch_results) == 1
    assert result.fetch_results[0].errors == ["No match"]


class StubEnricher:
    def enrich(self, record: SourceBookRecord) -> EnrichmentResult:
        return EnrichmentResult(
            isbn=record.isbn,
            source_name=record.source_name,
            applied=False,
            skipped_reason="no_enrichment_available",
        )


class StubGenerator:
    def generate(self, isbn: str, evidence) -> GeneratedSynopsis | None:
        return GeneratedSynopsis(
            text="Resumen generado a partir de evidencia textual suficiente y trazable del origen.",
            evidence_indexes=[0],
        )


class DummyResolvedSource:
    def fetch(self, isbn: str) -> FetchResult:
        return FetchResult(
            isbn=isbn,
            record=SourceBookRecord(
                source_name="google_books",
                isbn=isbn,
                title="Example Title",
                author="Example Author",
                editorial="Example Editorial",
                synopsis="Resumen del libro.",
                subject="FICCION",
            ),
            errors=[],
        )


def test_process_isbn_file_defaults_to_rules_only_mode(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")

    result = process_isbn_file(input_file, source=DummyResolvedSource())

    assert result.enrichment_results == [
        EnrichmentResult(isbn="9780306406157", skipped_reason="rules_only_mode")
    ]
    assert result.resolution_results[0].record is not None


def test_process_isbn_file_uses_configured_ai_mode(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")

    result = process_isbn_file(
        input_file,
        source=DummyResolvedSource(),
        config=AppConfig(execution_mode=ExecutionMode.AI_ENRICHED),
        enricher=StubEnricher(),
    )

    assert result.enrichment_results == [
        EnrichmentResult(
            isbn="9780306406157",
            source_name="google_books",
            applied=False,
            skipped_reason="no_enrichment_available",
                evidence=[
                    {
                        "source_name": "google_books",
                        "evidence_type": "source_synopsis",
                    "evidence_origin": "direct_source_record",
                    "text": "Resumen del libro.",
                    "source_url": None,
                    "language": None,
                        "extraction_method": "source_synopsis_field",
                        "quality_flags": ["trusted_source_synopsis", "unknown_language"],
                    },
                    {
                        "source_name": "google_books",
                        "evidence_type": "source_title",
                        "evidence_origin": "direct_source_record",
                        "text": "Example Title",
                        "source_url": None,
                        "language": None,
                        "extraction_method": "source_title_field",
                        "quality_flags": ["trusted_source_bibliographic_field", "title"],
                    },
                    {
                        "source_name": "google_books",
                        "evidence_type": "source_author",
                        "evidence_origin": "direct_source_record",
                        "text": "Example Author",
                        "source_url": None,
                        "language": None,
                        "extraction_method": "source_author_field",
                        "quality_flags": ["trusted_source_bibliographic_field", "author"],
                    },
                    {
                        "source_name": "google_books",
                        "evidence_type": "source_editorial",
                        "evidence_origin": "direct_source_record",
                        "text": "Example Editorial",
                        "source_url": None,
                        "language": None,
                        "extraction_method": "source_editorial_field",
                        "quality_flags": ["trusted_source_bibliographic_field", "editorial"],
                    },
                ],
            )
        ]


class DummyNonSpanishSynopsisSource:
    def fetch(self, isbn: str) -> FetchResult:
        return FetchResult(
            isbn=isbn,
            record=SourceBookRecord(
                source_name="google_books",
                isbn=isbn,
                title="Example Title",
                author="Example Author",
                editorial="Example Editorial",
                synopsis=(
                    "This detailed source description provides enough grounded evidence to produce "
                    "a Spanish synopsis without inventing metadata."
                ),
                language="en",
                subject="FICCION",
            ),
            errors=[],
        )


class DummyResolvableWithoutAiSource:
    def fetch(self, isbn: str) -> FetchResult:
        return FetchResult(
            isbn=isbn,
            record=SourceBookRecord(
                source_name="google_books",
                isbn=isbn,
                title="Example Title",
                author="Example Author",
                editorial="Example Editorial",
                synopsis="Resumen del libro.",
                subject="FICCION",
            ),
            errors=[],
        )


def test_process_isbn_file_applies_generator_in_ai_mode(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")

    result = process_isbn_file(
        input_file,
        source=DummyNonSpanishSynopsisSource(),
        config=AppConfig(execution_mode=ExecutionMode.AI_ENRICHED),
        generator=StubGenerator(),
    )

    assert result.fetch_results[0].record is not None
    assert result.fetch_results[0].record.synopsis == (
        "Resumen generado a partir de evidencia textual suficiente y trazable del origen."
    )
    assert result.fetch_results[0].record.language == "es"
    assert result.resolution_results[0].record is not None


def test_process_isbn_file_preserves_rules_only_resolution_when_ai_does_not_apply(
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")

    result = process_isbn_file(
        input_file,
        source=DummyResolvableWithoutAiSource(),
        config=AppConfig(execution_mode=ExecutionMode.AI_ENRICHED),
        enricher=StubEnricher(),
    )

    assert result.fetch_results[0].record is not None
    assert result.fetch_results[0].record.synopsis == "Resumen del libro."
    assert result.resolution_results[0].record is not None
    assert result.resolution_results[0].record.synopsis == "Resumen del libro."
    assert result.enrichment_results[0].skipped_reason == "no_enrichment_available"


def test_attach_enrichment_results_adds_matching_enrichment_to_each_resolution() -> None:
    resolution_results = [
        ResolutionResult(
            record=None,
            source_record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
            ),
            errors=["Synopsis is missing."],
        )
    ]
    enrichment_results = [
        EnrichmentResult(
            isbn="9780306406157",
            skipped_reason="rules_only_mode",
        )
    ]

    attached_results = _attach_enrichment_results(
        resolution_results,
        enrichment_results,
    )

    assert attached_results[0].enrichment_result == enrichment_results[0]
    assert resolution_results[0].enrichment_result is None


def test_select_best_resolution_results_prefers_enriched_resolution_when_available() -> None:
    baseline_results = [
        ResolutionResult(
            record=None,
            source_record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
            ),
            errors=["Synopsis is missing."],
            reason_codes=["MISSING_SYNOPSIS"],
        )
    ]
    enriched_results = [
        ResolutionResult(
            record=BookRecord(
                isbn="9780306406157",
                title="Example Title",
                author="Example Author",
                editorial="Example Editorial",
                synopsis="Resumen del libro.",
                subject="FICCION",
            ),
            source_record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
            ),
            errors=[],
        )
    ]

    selected_results = _select_best_resolution_results(
        baseline_results,
        enriched_results,
    )

    assert selected_results == enriched_results


def test_select_best_resolution_results_preserves_baseline_resolution_when_enriched_fails() -> None:
    baseline_results = [
        ResolutionResult(
            record=BookRecord(
                isbn="9780306406157",
                title="Example Title",
                author="Example Author",
                editorial="Example Editorial",
                synopsis="Resumen del libro.",
                subject="FICCION",
            ),
            source_record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
            ),
            errors=[],
        )
    ]
    enriched_results = [
        ResolutionResult(
            record=None,
            source_record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
            ),
            errors=["Generated synopsis rejected."],
            reason_codes=["MISSING_SYNOPSIS"],
        )
    ]

    selected_results = _select_best_resolution_results(
        baseline_results,
        enriched_results,
    )

    assert selected_results == baseline_results


def test_select_best_resolution_results_keeps_unresolved_enriched_result_when_both_fail() -> None:
    baseline_results = [
        ResolutionResult(
            record=None,
            source_record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
            ),
            errors=["Synopsis is missing."],
            reason_codes=["MISSING_SYNOPSIS"],
        )
    ]
    enriched_results = [
        ResolutionResult(
            record=None,
            source_record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
            ),
            errors=["Subject is missing."],
            reason_codes=["MISSING_SUBJECT"],
        )
    ]

    selected_results = _select_best_resolution_results(
        baseline_results,
        enriched_results,
    )

    assert selected_results == enriched_results


@patch("book_store_assistant.pipeline.service.fetch_all")
def test_process_isbn_file_passes_fetch_callbacks_through_to_fetch_layer(
    mock_fetch_all,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")
    mock_fetch_all.return_value = []

    def on_fetch_start(index: int, total: int, isbn: str) -> None:
        return None

    def on_fetch_complete(index: int, total: int, result: FetchResult) -> None:
        return None

    process_isbn_file(
        input_file,
        on_fetch_start=on_fetch_start,
        on_fetch_complete=on_fetch_complete,
    )

    assert mock_fetch_all.call_args.kwargs["on_fetch_start"] is on_fetch_start
    assert mock_fetch_all.call_args.kwargs["on_fetch_complete"] is on_fetch_complete


@patch("book_store_assistant.pipeline.service.enrich_fetch_results")
@patch("book_store_assistant.pipeline.service.fetch_all")
def test_process_isbn_file_passes_enrichment_callbacks_through_to_enrichment_layer(
    mock_fetch_all,
    mock_enrich_fetch_results,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")
    mock_fetch_all.return_value = []
    mock_enrich_fetch_results.return_value = ([], [])

    def on_enrichment_start(index: int, total: int, isbn: str) -> None:
        return None

    def on_enrichment_complete(index: int, total: int, result: EnrichmentResult) -> None:
        return None

    process_isbn_file(
        input_file,
        on_enrichment_start=on_enrichment_start,
        on_enrichment_complete=on_enrichment_complete,
    )

    assert (
        mock_enrich_fetch_results.call_args.kwargs["on_enrichment_start"]
        is on_enrichment_start
    )
    assert (
        mock_enrich_fetch_results.call_args.kwargs["on_enrichment_complete"]
        is on_enrichment_complete
    )


@patch("book_store_assistant.pipeline.service.enrich_fetch_results")
@patch("book_store_assistant.pipeline.service.fetch_all")
def test_process_isbn_file_explicit_mode_overrides_configured_mode(
    mock_fetch_all,
    mock_enrich_fetch_results,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")
    mock_fetch_all.return_value = []
    mock_enrich_fetch_results.return_value = (
        [],
        [],
    )

    process_isbn_file(
        input_file,
        config=AppConfig(execution_mode=ExecutionMode.AI_ENRICHED),
        mode=ExecutionMode.RULES_ONLY,
    )

    assert mock_enrich_fetch_results.call_args.kwargs["mode"] is ExecutionMode.RULES_ONLY
