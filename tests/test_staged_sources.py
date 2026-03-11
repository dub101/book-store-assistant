from pathlib import Path
from unittest.mock import patch

from book_store_assistant.config import AppConfig
from book_store_assistant.pipeline.contracts import ISBNInput
from book_store_assistant.sources.cache import FetchResultCache
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.staged import fetch_with_intermediate_stages


def test_fetch_with_intermediate_stages_skips_downstream_sources_for_complete_cached_records(
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "sample.csv"
    input_file.write_text("9780306406157\n9780306406158\n", encoding="utf-8")
    config = AppConfig(
        source_cache_dir=tmp_path / "cache",
        intermediate_dir=tmp_path / "intermediate",
        source_request_pause_seconds=0.0,
        open_library_batch_size=10,
    )
    cache = FetchResultCache(config.source_cache_dir, "staged_fetch_v1")
    cache.set(
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="cached_source",
                isbn="9780306406157",
                title="Cached Title",
                author="Cached Author",
                editorial="Cached Editorial",
                synopsis="Resumen ya disponible.",
                subject="FICCION",
            ),
            errors=[],
        )
    )

    with (
        patch("book_store_assistant.sources.staged.BneSruSource.fetch") as mock_bne,
        patch("book_store_assistant.sources.staged.OpenLibrarySource.fetch_batch") as mock_batch,
        patch("book_store_assistant.sources.staged.GoogleBooksSource.fetch") as mock_google,
    ):
        mock_bne.return_value = FetchResult(
            isbn="9780306406158",
            record=SourceBookRecord(
                source_name="bne",
                isbn="9780306406158",
                title="BNE Title",
            ),
            errors=[],
        )
        mock_batch.return_value = [
            FetchResult(
                isbn="9780306406158",
                record=SourceBookRecord(
                    source_name="open_library",
                    isbn="9780306406158",
                    title="Open Library Title",
                ),
                errors=[],
            )
        ]
        mock_google.return_value = FetchResult(
            isbn="9780306406158",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406158",
                title="Open Library Title",
                author="Google Author",
                editorial="Google Editorial",
            ),
            errors=[],
        )

        results = fetch_with_intermediate_stages(
            input_file,
            [
                ISBNInput(isbn="9780306406157"),
                ISBNInput(isbn="9780306406158"),
            ],
            config,
        )

    mock_bne.assert_called_once_with("9780306406158")
    assert mock_batch.call_args.args[0] == ["9780306406158"]
    mock_google.assert_called_once_with("9780306406158")
    assert results[0].record is not None
    assert results[0].record.title == "Cached Title"
    assert results[1].record is not None
    assert results[1].record.title == "BNE Title"
    assert results[1].record.author == "Google Author"
    assert (config.intermediate_dir / "sample.cache.jsonl").exists()
    assert (config.intermediate_dir / "sample.bne.jsonl").exists()
    assert (config.intermediate_dir / "sample.open_library.jsonl").exists()
    assert (config.intermediate_dir / "sample.google_books.jsonl").exists()


def test_fetch_with_intermediate_stages_fetches_google_when_synopsis_is_still_missing(
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "sample.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")
    config = AppConfig(
        source_cache_dir=tmp_path / "cache",
        intermediate_dir=tmp_path / "intermediate",
        source_request_pause_seconds=0.0,
        open_library_batch_size=10,
    )
    cache = FetchResultCache(config.source_cache_dir, "staged_fetch_v1")
    cache.set(
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="cached_source",
                isbn="9780306406157",
                title="Cached Title",
                author="Cached Author",
                editorial="Cached Editorial",
            ),
            errors=[],
        )
    )

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
                title="Cached Title",
                author="Cached Author",
                editorial="Cached Editorial",
            ),
            errors=[],
        )
        mock_batch.return_value = [
            FetchResult(
                isbn="9780306406157",
                record=SourceBookRecord(
                    source_name="open_library",
                    isbn="9780306406157",
                    categories=["Narrative fiction"],
                ),
                errors=[],
            )
        ]
        mock_google.return_value = FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Cached Title",
                author="Cached Author",
                editorial="Cached Editorial",
            ),
            errors=[],
        )

        results = fetch_with_intermediate_stages(
            input_file,
            [ISBNInput(isbn="9780306406157")],
            config,
        )

    mock_bne.assert_called_once_with("9780306406157")
    assert mock_batch.call_args.args[0] == ["9780306406157"]
    mock_google.assert_called_once_with("9780306406157")
    assert results[0].record is not None
    assert results[0].record.categories == ["Narrative fiction"]


def test_fetch_with_intermediate_stages_skips_bne_when_disabled(tmp_path: Path) -> None:
    input_file = tmp_path / "sample.csv"
    input_file.write_text("9780306406157\n", encoding="utf-8")
    config = AppConfig(
        source_cache_dir=tmp_path / "cache",
        intermediate_dir=tmp_path / "intermediate",
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
                    categories=["Narrative fiction"],
                ),
                errors=[],
            )
        ]
        mock_google.return_value = FetchResult(
            isbn="9780306406157",
            record=None,
            errors=["No Google Books match found."],
            issue_codes=["GOOGLE_BOOKS_NO_MATCH"],
        )

        results = fetch_with_intermediate_stages(
            input_file,
            [ISBNInput(isbn="9780306406157")],
            config,
        )

    mock_bne.assert_not_called()
    assert results[0].record is not None
    assert results[0].record.title == "Open Library Title"
