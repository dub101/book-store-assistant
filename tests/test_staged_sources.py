from unittest.mock import patch

from book_store_assistant.config import AppConfig
from book_store_assistant.pipeline.contracts import ISBNInput
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.staged import fetch_with_stages


def _make_national_source_mock(isbn: str, title: str | None = None):
    """Return a mock national source whose fetch() returns a record with *title*."""
    from unittest.mock import MagicMock

    from book_store_assistant.sources.national.base import StubNationalSource

    source = MagicMock(spec=StubNationalSource)
    source.source_name = "bne"
    if title is not None:
        source.fetch.return_value = FetchResult(
            isbn=isbn,
            record=SourceBookRecord(
                source_name="bne",
                isbn=isbn,
                title=title,
            ),
            errors=[],
        )
    else:
        source.fetch.return_value = FetchResult(
            isbn=isbn, record=None, errors=[], issue_codes=[]
        )
    return source


def test_fetch_with_stages_queries_sources_for_incomplete_bibliographic_records() -> None:
    config = AppConfig(source_request_pause_seconds=0.0, open_library_batch_size=10)

    national_source = _make_national_source_mock("9780306406157", title="National Title")

    with (
        patch(
            "book_store_assistant.sources.staged.get_national_source",
            return_value=national_source,
        ),
        patch("book_store_assistant.sources.staged.OpenLibrarySource.fetch_batch") as mock_batch,
        patch("book_store_assistant.sources.staged.GoogleBooksSource.fetch") as mock_google,
    ):
        mock_batch.return_value = [
            FetchResult(
                isbn="9780306406157",
                record=SourceBookRecord(
                    source_name="open_library",
                    isbn="9780306406157",
                    title="National Title",
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
                title="National Title",
                author="Open Library Author",
                editorial="Google Editorial",
            ),
            errors=[],
        )

        results = fetch_with_stages(
            [ISBNInput(isbn="9780306406157")],
            config,
        )

    national_source.fetch.assert_called_once_with("9780306406157")
    assert mock_batch.call_args.args[0] == ["9780306406157"]
    mock_google.assert_called_once_with("9780306406157")
    assert results[0].record is not None
    assert results[0].record.title == "National Title"
    assert results[0].record.author == "Open Library Author"
    assert results[0].record.editorial == "Google Editorial"


def test_fetch_with_stages_skips_national_routing_when_disabled() -> None:
    config = AppConfig(
        source_request_pause_seconds=0.0,
        open_library_batch_size=10,
        national_agency_routing_enabled=False,
    )

    with (
        patch(
            "book_store_assistant.sources.staged.get_national_source",
        ) as mock_get_national,
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
            [ISBNInput(isbn="9780306406157")],
            config,
        )

    mock_get_national.assert_not_called()
    assert results[0].record is not None
    assert results[0].record.title == "Open Library Title"


def test_fetch_with_stages_skips_google_once_bibliographic_fields_are_complete() -> None:
    config = AppConfig(source_request_pause_seconds=0.0, open_library_batch_size=10)

    national_source = _make_national_source_mock("9780306406157", title="Complete Title")
    national_source.fetch.return_value = FetchResult(
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

    with (
        patch(
            "book_store_assistant.sources.staged.get_national_source",
            return_value=national_source,
        ),
        patch("book_store_assistant.sources.staged.OpenLibrarySource.fetch_batch") as mock_batch,
        patch("book_store_assistant.sources.staged.GoogleBooksSource.fetch") as mock_google,
    ):
        mock_batch.return_value = []

        results = fetch_with_stages(
            [ISBNInput(isbn="9780306406157")],
            config,
        )

    national_source.fetch.assert_called_once_with("9780306406157")
    mock_batch.assert_not_called()
    mock_google.assert_not_called()
    assert results[0].record is not None
    assert results[0].record.title == "Complete Title"
