from pathlib import Path
from unittest.mock import patch

from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.config import AppConfig
from book_store_assistant.pipeline.service import process_isbn_file
from book_store_assistant.resolution.models import RecordValidationAssessment
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


class DummySource:
    def fetch(self, isbn: str) -> FetchResult:
        return FetchResult(
            isbn=isbn,
            record=SourceBookRecord(
                source_name="google_books",
                isbn=isbn,
                title="Example Title",
                subtitle="Example Subtitle",
                author="Example Author",
                editorial="Debolsillo",
                synopsis="Sinopsis de ejemplo en español.",
                subject="NOVELA",
                subject_code="20",
                language="es",
            ),
            errors=[],
        )


class AcceptingValidator:
    def validate(self, source_record, candidate_record):
        assert candidate_record.title == "Example Title"
        return RecordValidationAssessment(accepted=True, confidence=0.97)


def test_process_isbn_file_uses_injected_source_and_resolves_bibliographic_record(
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\ninvalid\n", encoding="utf-8")

    with patch(
        "book_store_assistant.pipeline.service.build_default_record_quality_validator",
        return_value=AcceptingValidator(),
    ), patch(
        "book_store_assistant.pipeline.service.build_default_llm_enricher",
        return_value=None,
    ):
        result = process_isbn_file(input_file, source=DummySource(), config=AppConfig())

    assert len(result.input_result.valid_inputs) == 1
    assert result.input_result.invalid_values == ["invalid"]
    assert len(result.fetch_results) == 1
    assert isinstance(result.resolution_results[0].record, BibliographicRecord)
    assert result.resolution_results[0].record.editorial == "Debolsillo"
    assert result.resolution_results[0].record.synopsis == "Sinopsis de ejemplo en español."
    assert result.resolution_results[0].record.subject == "NOVELA"
    assert result.resolution_results[0].record.subject_code == "20"


def test_process_isbn_file_runs_llm_enrichment_stage(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")

    initial_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Example Title",
                author=None,
                editorial=None,
            ),
            errors=[],
            issue_codes=[],
        )
    ]

    enrichment_calls: list[str] = []

    class TrackingEnricher:
        def enrich(self, isbn, partial):
            enrichment_calls.append(isbn)
            return None

    with patch(
        "book_store_assistant.pipeline.service.build_default_record_quality_validator",
        return_value=AcceptingValidator(),
    ), patch(
        "book_store_assistant.pipeline.service.build_default_llm_enricher",
        return_value=TrackingEnricher(),
    ), patch(
        "book_store_assistant.pipeline.service.fetch_all",
        return_value=initial_results,
    ):
        process_isbn_file(input_file, source=DummySource(), config=AppConfig())

    assert "9780306406157" in enrichment_calls


def test_process_isbn_file_skips_enrichment_when_enricher_is_none(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")

    with patch(
        "book_store_assistant.pipeline.service.build_default_record_quality_validator",
        return_value=AcceptingValidator(),
    ), patch(
        "book_store_assistant.pipeline.service.build_default_llm_enricher",
        return_value=None,
    ), patch(
        "book_store_assistant.pipeline.service.augment_fetch_results_with_llm_enrichment"
    ) as mock_enrich:
        process_isbn_file(input_file, source=DummySource(), config=AppConfig())

    mock_enrich.assert_not_called()
