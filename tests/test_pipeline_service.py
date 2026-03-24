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
            ),
            errors=[],
        )


class AcceptingValidator:
    def validate(self, source_record, candidate_record, publisher_identity=None):
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
    assert result.fetch_results[0].publisher_identity is not None
    assert (
        result.fetch_results[0].publisher_identity.publisher_name
        == "Penguin Random House Grupo Editorial"
    )
    assert isinstance(result.resolution_results[0].record, BibliographicRecord)
    assert result.resolution_results[0].record.editorial == "Debolsillo"
    assert (
        result.resolution_results[0].record.publisher
        == "Penguin Random House Grupo Editorial"
    )


@patch("book_store_assistant.pipeline.service.augment_fetch_results_with_retailer_editorials")
@patch("book_store_assistant.pipeline.service.augment_fetch_results_with_publisher_discovery")
@patch("book_store_assistant.pipeline.service.augment_fetch_results_with_publisher_pages")
@patch("book_store_assistant.pipeline.service.augment_fetch_results_with_editorial_search")
@patch("book_store_assistant.pipeline.service.augment_fetch_results_with_source_pages")
def test_process_isbn_file_runs_simplified_retrieval_order(
    mock_augment_fetch_results_with_source_pages,
    mock_augment_fetch_results_with_editorial_search,
    mock_augment_publisher_pages,
    mock_augment_publisher_discovery,
    mock_augment_retailer_editorials,
    tmp_path: Path,
) -> None:
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
    stage_order: list[str] = []

    def source_pages(results, **kwargs):
        stage_order.append("source_pages")
        del kwargs
        return results

    def general_web_search(results, **kwargs):
        stage_order.append("web_search_editorial")
        del kwargs
        return [
            FetchResult(
                isbn="9780306406157",
                record=SourceBookRecord(
                    source_name="google_books + web_search",
                    isbn="9780306406157",
                    title="Example Title",
                    author=None,
                    editorial="Planeta",
                ),
                errors=[],
                issue_codes=[],
            )
        ]

    def publisher_pages(results, **kwargs):
        stage_order.append("publisher_pages")
        assert kwargs["eligible_isbns"] == {"9780306406157"}
        return results

    def retailer_lookup(results, **kwargs):
        stage_order.append("retailer_lookup")
        del kwargs
        return results

    def publisher_discovery(results, **kwargs):
        stage_order.append("publisher_discovery")
        del kwargs
        return results

    mock_augment_fetch_results_with_source_pages.side_effect = source_pages
    mock_augment_fetch_results_with_editorial_search.side_effect = general_web_search
    mock_augment_publisher_pages.side_effect = publisher_pages
    mock_augment_retailer_editorials.side_effect = retailer_lookup
    mock_augment_publisher_discovery.side_effect = publisher_discovery

    with patch(
        "book_store_assistant.pipeline.service.build_default_record_quality_validator",
        return_value=AcceptingValidator(),
    ), patch(
        "book_store_assistant.pipeline.service.fetch_all",
        return_value=initial_results,
    ), patch(
        "book_store_assistant.pipeline.service.build_default_bibliographic_extractor",
        return_value=object(),
    ):
        process_isbn_file(input_file, source=DummySource(), config=AppConfig())

    assert stage_order == [
        "source_pages",
        "web_search_editorial",
        "publisher_pages",
        "retailer_lookup",
        "publisher_discovery",
    ]


@patch("book_store_assistant.pipeline.service.augment_fetch_results_with_editorial_search")
def test_process_isbn_file_runs_editorial_web_search_before_resolution(
    mock_augment_fetch_results_with_editorial_search,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")
    initial_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="bne",
                isbn="9780306406157",
                title="BNE Title",
                author=None,
                editorial="Barcelona, Planeta",
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    mock_augment_fetch_results_with_editorial_search.return_value = initial_results

    with (
        patch(
            "book_store_assistant.pipeline.service.fetch_all",
            return_value=initial_results,
        ),
        patch(
            "book_store_assistant.pipeline.service.build_default_record_quality_validator",
            return_value=AcceptingValidator(),
        ),
        patch(
            "book_store_assistant.pipeline.service.build_default_bibliographic_extractor",
            return_value=object(),
        ),
    ):
        process_isbn_file(
            input_file,
            source=DummySource(),
            config=AppConfig(web_search_max_retries=3),
        )

    assert mock_augment_fetch_results_with_editorial_search.call_count == 1
    first_call = mock_augment_fetch_results_with_editorial_search.call_args_list[0]
    assert first_call.kwargs["max_retries"] == 3
