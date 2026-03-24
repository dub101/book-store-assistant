from pathlib import Path
from unittest.mock import patch

from book_store_assistant.config import AppConfig
from book_store_assistant.pipeline.contracts import ISBNInput
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.staged import fetch_with_stages


def test_fetch_with_stages_queries_sources_for_incomplete_bibliographic_records(
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "sample.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")
    config = AppConfig(source_request_pause_seconds=0.0, open_library_batch_size=10)

    with (
        patch("book_store_assistant.sources.staged.BneSruSource.fetch") as mock_bne,
        patch("book_store_assistant.sources.staged.OpenLibrarySource.fetch_batch") as mock_batch,
        patch("book_store_assistant.sources.staged.GoogleBooksSource.fetch") as mock_google,
    ):
        mock_bne.return_value = FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="bne",
                isbn="9780306406157",
                title="BNE Title",
            ),
            errors=[],
        )
        mock_batch.return_value = [
            FetchResult(
                isbn="9780306406157",
                record=SourceBookRecord(
                    source_name="open_library",
                    isbn="9780306406157",
                    title="BNE Title",
                    author="Open Library Author",
                ),
                errors=[],
            )
        ]
        mock_google.return_value = FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="BNE Title",
                author="Open Library Author",
                editorial="Google Editorial",
            ),
            errors=[],
        )

        results = fetch_with_stages(
            input_file,
            [ISBNInput(isbn="9780306406157")],
            config,
        )

    mock_bne.assert_called_once_with("9780306406157")
    assert mock_batch.call_args.args[0] == ["9780306406157"]
    mock_google.assert_called_once_with("9780306406157")
    assert results[0].record is not None
    assert results[0].record.title == "BNE Title"
    assert results[0].record.author == "Open Library Author"
    assert results[0].record.editorial == "Google Editorial"


def test_fetch_with_stages_skips_bne_when_disabled(tmp_path: Path) -> None:
    input_file = tmp_path / "sample.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")
    config = AppConfig(
        source_request_pause_seconds=0.0,
        open_library_batch_size=10,
        bne_lookup_enabled=False,
    )

    with (
        patch("book_store_assistant.sources.staged.BneSruSource.fetch") as mock_bne,
        patch("book_store_assistant.sources.staged.OpenLibrarySource.fetch_batch") as mock_batch,
        patch("book_store_assistant.sources.staged.GoogleBooksSource.fetch") as mock_google,
    ):
        mock_batch.return_value = [
            FetchResult(
                isbn="9780306406157",
                record=SourceBookRecord(
                    source_name="open_library",
                    isbn="9780306406157",
                    title="Open Library Title",
                    author="Open Library Author",
                    editorial="Open Library Editorial",
                ),
                errors=[],
            )
        ]
        mock_google.return_value = FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Open Library Title",
                author="Open Library Author",
                editorial="Open Library Editorial",
            ),
            errors=[],
        )

        results = fetch_with_stages(
            input_file,
            [ISBNInput(isbn="9780306406157")],
            config,
        )

    mock_bne.assert_not_called()
    assert results[0].record is not None
    assert results[0].record.title == "Open Library Title"


def test_fetch_with_stages_skips_google_once_bibliographic_fields_are_complete(
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "sample.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")
    config = AppConfig(source_request_pause_seconds=0.0, open_library_batch_size=10)

    with (
        patch("book_store_assistant.sources.staged.BneSruSource.fetch") as mock_bne,
        patch("book_store_assistant.sources.staged.OpenLibrarySource.fetch_batch") as mock_batch,
        patch("book_store_assistant.sources.staged.GoogleBooksSource.fetch") as mock_google,
    ):
        mock_bne.return_value = FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="bne",
                isbn="9780306406157",
                title="Complete Title",
                author="Complete Author",
                editorial="Complete Editorial",
            ),
            errors=[],
        )
        mock_batch.return_value = []

        results = fetch_with_stages(
            input_file,
            [ISBNInput(isbn="9780306406157")],
            config,
        )

    mock_bne.assert_called_once_with("9780306406157")
    mock_batch.assert_not_called()
    mock_google.assert_not_called()
    assert results[0].record is not None
    assert results[0].record.title == "Complete Title"
