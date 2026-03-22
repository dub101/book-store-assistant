from pathlib import Path
from unittest.mock import patch

from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.config import AppConfig
from book_store_assistant.pipeline.service import process_isbn_file
from book_store_assistant.publisher_identity.models import PublisherIdentityResult
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
    ):
        result = process_isbn_file(input_file, source=DummySource(), config=AppConfig())

    assert len(result.input_result.valid_inputs) == 1
    assert result.input_result.invalid_values == ["invalid"]
    assert len(result.fetch_results) == 1
    assert result.publisher_identity_results == [
        PublisherIdentityResult(
            isbn="9780306406157",
            publisher_name="Debolsillo",
            imprint_name="Debolsillo",
            publisher_group_key="penguin_random_house",
            source_name="google_books",
            source_field="editorial",
            confidence=0.95,
            resolution_method="editorial_field",
            evidence=["editorial:Debolsillo"],
        )
    ]
    assert isinstance(result.resolution_results[0].record, BibliographicRecord)
    assert result.resolution_results[0].record.publisher == "Debolsillo"


@patch("book_store_assistant.pipeline.service.augment_fetch_results_with_retailer_editorials")
@patch("book_store_assistant.pipeline.service.augment_fetch_results_with_publisher_pages")
def test_process_isbn_file_retries_publisher_lookup_after_retailer_editorial_unlock(
    mock_augment_publisher_pages,
    mock_augment_retailer_editorials,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")

    mock_augment_retailer_editorials.return_value = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books + retailer_page:casa_del_libro",
                isbn="9780306406157",
                title="Example Title",
                editorial="Planeta",
                field_sources={"editorial": "retailer_page:casa_del_libro"},
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    mock_augment_publisher_pages.return_value = mock_augment_retailer_editorials.return_value

    with patch(
        "book_store_assistant.pipeline.service.build_default_record_quality_validator",
        return_value=AcceptingValidator(),
    ):
        process_isbn_file(input_file, source=DummySource(), config=AppConfig())

    assert mock_augment_publisher_pages.call_count == 1
    assert mock_augment_publisher_pages.call_args.kwargs["eligible_isbns"] == {
        "9780306406157"
    }
