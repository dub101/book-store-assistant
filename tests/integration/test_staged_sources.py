from unittest.mock import MagicMock, patch

from book_store_assistant.config import AppConfig
from book_store_assistant.pipeline.contracts import ISBNInput
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.staged import (
    _chunked,
    _has_text,
    _merge_stage_results,
    _needs_additional_metadata,
    _prefix_result,
    fetch_with_stages,
)


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


# ---------------------------------------------------------------------------
# Tests for _prefix_result
# ---------------------------------------------------------------------------


class TestPrefixResult:
    def test_prefixes_errors_with_source_name(self) -> None:
        result = FetchResult(
            isbn="9780306406157",
            record=None,
            errors=["timeout", "bad response"],
            issue_codes=["TIMEOUT"],
        )
        prefixed = _prefix_result(result, "google_books")
        assert prefixed.errors == ["google_books: timeout", "google_books: bad response"]
        assert prefixed.issue_codes == ["GOOGLE_BOOKS:TIMEOUT"]

    def test_preserves_record_and_isbn(self) -> None:
        record = SourceBookRecord(
            source_name="open_library", isbn="9780306406157", title="A Title"
        )
        result = FetchResult(isbn="9780306406157", record=record, errors=[], issue_codes=[])
        prefixed = _prefix_result(result, "open_library")
        assert prefixed.isbn == "9780306406157"
        assert prefixed.record is not None
        assert prefixed.record.title == "A Title"

    def test_handles_empty_errors_and_issue_codes(self) -> None:
        result = FetchResult(isbn="9780306406157", record=None, errors=[], issue_codes=[])
        prefixed = _prefix_result(result, "isbndb")
        assert prefixed.errors == []
        assert prefixed.issue_codes == []


# ---------------------------------------------------------------------------
# Tests for _merge_stage_results
# ---------------------------------------------------------------------------


class TestMergeStageResults:
    def test_no_successful_records_returns_none_record(self) -> None:
        r1 = FetchResult(
            isbn="9780306406157", record=None, errors=["err1"], issue_codes=["IC1"]
        )
        r2 = FetchResult(
            isbn="9780306406157", record=None, errors=["err2"], issue_codes=["IC2"]
        )
        merged = _merge_stage_results(r1, r2)
        assert merged.record is None
        assert merged.isbn == "9780306406157"
        assert merged.errors == ["err1", "err2"]
        assert merged.issue_codes == ["IC1", "IC2"]

    def test_multiple_records_merged(self) -> None:
        rec1 = SourceBookRecord(
            source_name="open_library",
            isbn="9780306406157",
            title="OL Title",
            author="OL Author",
        )
        rec2 = SourceBookRecord(
            source_name="google_books",
            isbn="9780306406157",
            editorial="Google Editorial",
        )
        r1 = FetchResult(isbn="9780306406157", record=rec1, errors=["err1"], issue_codes=[])
        r2 = FetchResult(isbn="9780306406157", record=rec2, errors=["err2"], issue_codes=[])
        merged = _merge_stage_results(r1, r2)
        assert merged.record is not None
        assert merged.record.title == "OL Title"
        assert merged.record.author == "OL Author"
        assert merged.record.editorial == "Google Editorial"
        assert merged.errors == ["err1", "err2"]

    def test_deduplicates_errors_and_issue_codes(self) -> None:
        r1 = FetchResult(
            isbn="9780306406157",
            record=None,
            errors=["same error"],
            issue_codes=["SAME_CODE"],
        )
        r2 = FetchResult(
            isbn="9780306406157",
            record=None,
            errors=["same error"],
            issue_codes=["SAME_CODE"],
        )
        merged = _merge_stage_results(r1, r2)
        assert merged.errors == ["same error"]
        assert merged.issue_codes == ["SAME_CODE"]

    def test_single_result_with_record(self) -> None:
        rec = SourceBookRecord(
            source_name="isbndb", isbn="9780306406157", title="ISBNdb Title"
        )
        r1 = FetchResult(isbn="9780306406157", record=rec, errors=[], issue_codes=[])
        merged = _merge_stage_results(r1)
        assert merged.record is not None
        assert merged.record.title == "ISBNdb Title"


# ---------------------------------------------------------------------------
# Tests for _has_text and _chunked
# ---------------------------------------------------------------------------


class TestHasText:
    def test_returns_true_for_non_empty_string(self) -> None:
        assert _has_text("hello") is True

    def test_returns_false_for_none(self) -> None:
        assert _has_text(None) is False

    def test_returns_false_for_whitespace_only(self) -> None:
        assert _has_text("   ") is False

    def test_returns_false_for_empty_string(self) -> None:
        assert _has_text("") is False


class TestChunked:
    def test_returns_single_chunk_when_size_is_zero(self) -> None:
        result = _chunked(["a", "b", "c"], 0)
        assert result == [["a", "b", "c"]]

    def test_chunks_into_expected_groups(self) -> None:
        result = _chunked(["a", "b", "c", "d", "e"], 2)
        assert result == [["a", "b"], ["c", "d"], ["e"]]


# ---------------------------------------------------------------------------
# Tests for _needs_additional_metadata
# ---------------------------------------------------------------------------


class TestNeedsAdditionalMetadata:
    def test_returns_true_when_result_is_none(self) -> None:
        assert _needs_additional_metadata(None) is True

    def test_returns_true_when_record_is_none(self) -> None:
        result = FetchResult(isbn="9780306406157", record=None, errors=[])
        assert _needs_additional_metadata(result) is True

    def test_returns_false_when_all_fields_present(self) -> None:
        rec = SourceBookRecord(
            source_name="test",
            isbn="9780306406157",
            title="Title",
            author="Author",
            editorial="Editorial",
        )
        result = FetchResult(isbn="9780306406157", record=rec, errors=[])
        assert _needs_additional_metadata(result) is False

    def test_returns_true_when_editorial_missing(self) -> None:
        rec = SourceBookRecord(
            source_name="test",
            isbn="9780306406157",
            title="Title",
            author="Author",
        )
        result = FetchResult(isbn="9780306406157", record=rec, errors=[])
        assert _needs_additional_metadata(result) is True


# ---------------------------------------------------------------------------
# Tests for fetch_with_stages with ISBNdb enabled
# ---------------------------------------------------------------------------


class TestFetchWithStagesISBNdb:
    def test_isbndb_runs_first_when_enabled(self) -> None:
        config = AppConfig(
            source_request_pause_seconds=0.0,
            open_library_batch_size=10,
            isbndb_lookup_enabled=True,
            isbndb_api_key="test-key",
        )

        with (
            patch(
                "book_store_assistant.sources.staged.get_national_source",
                return_value=None,
            ),
            patch(
                "book_store_assistant.sources.staged.ISBNdbSource.fetch"
            ) as mock_isbndb_fetch,
            patch(
                "book_store_assistant.sources.staged.OpenLibrarySource.fetch_batch"
            ) as mock_batch,
            patch(
                "book_store_assistant.sources.staged.GoogleBooksSource.fetch"
            ) as mock_google,
        ):
            mock_isbndb_fetch.return_value = FetchResult(
                isbn="9780306406157",
                record=SourceBookRecord(
                    source_name="isbndb",
                    isbn="9780306406157",
                    title="ISBNdb Title",
                    author="ISBNdb Author",
                    editorial="ISBNdb Editorial",
                ),
                errors=[],
                issue_codes=[],
            )
            mock_batch.return_value = []

            results = fetch_with_stages(
                [ISBNInput(isbn="9780306406157")],
                config,
            )

        mock_isbndb_fetch.assert_called_once_with("9780306406157")
        # Complete record from ISBNdb means OL and Google are skipped
        mock_batch.assert_not_called()
        mock_google.assert_not_called()
        assert results[0].record is not None
        assert results[0].record.title == "ISBNdb Title"
        assert results[0].record.author == "ISBNdb Author"
        assert results[0].record.editorial == "ISBNdb Editorial"

    def test_isbndb_incomplete_record_triggers_later_stages(self) -> None:
        config = AppConfig(
            source_request_pause_seconds=0.0,
            open_library_batch_size=10,
            isbndb_lookup_enabled=True,
            isbndb_api_key="test-key",
            national_agency_routing_enabled=False,
        )

        with (
            patch(
                "book_store_assistant.sources.staged.ISBNdbSource.fetch"
            ) as mock_isbndb_fetch,
            patch(
                "book_store_assistant.sources.staged.OpenLibrarySource.fetch_batch"
            ) as mock_batch,
            patch(
                "book_store_assistant.sources.staged.GoogleBooksSource.fetch"
            ) as mock_google,
        ):
            mock_isbndb_fetch.return_value = FetchResult(
                isbn="9780306406157",
                record=SourceBookRecord(
                    source_name="isbndb",
                    isbn="9780306406157",
                    title="ISBNdb Title",
                ),
                errors=[],
                issue_codes=[],
            )
            mock_batch.return_value = [
                FetchResult(
                    isbn="9780306406157",
                    record=SourceBookRecord(
                        source_name="open_library",
                        isbn="9780306406157",
                        author="OL Author",
                    ),
                    errors=[],
                )
            ]
            mock_google.return_value = FetchResult(
                isbn="9780306406157",
                record=SourceBookRecord(
                    source_name="google_books",
                    isbn="9780306406157",
                    editorial="Google Editorial",
                ),
                errors=[],
            )

            results = fetch_with_stages(
                [ISBNInput(isbn="9780306406157")],
                config,
            )

        mock_isbndb_fetch.assert_called_once()
        mock_batch.assert_called_once()
        mock_google.assert_called_once()
        assert results[0].record is not None
        assert results[0].record.title == "ISBNdb Title"
        assert results[0].record.author == "OL Author"
        assert results[0].record.editorial == "Google Editorial"


# ---------------------------------------------------------------------------
# Tests for stage update and fetch callbacks
# ---------------------------------------------------------------------------


class TestFetchWithStagesCallbacks:
    def test_on_stage_update_called_at_each_stage(self) -> None:
        config = AppConfig(
            source_request_pause_seconds=0.0,
            open_library_batch_size=10,
            national_agency_routing_enabled=False,
        )
        stage_updates: list[str] = []
        on_stage_update = MagicMock(side_effect=lambda msg: stage_updates.append(msg))

        with (
            patch(
                "book_store_assistant.sources.staged.OpenLibrarySource.fetch_batch"
            ) as mock_batch,
            patch(
                "book_store_assistant.sources.staged.GoogleBooksSource.fetch"
            ) as mock_google,
        ):
            mock_batch.return_value = [
                FetchResult(
                    isbn="9780306406157",
                    record=SourceBookRecord(
                        source_name="open_library",
                        isbn="9780306406157",
                        title="Title",
                        author="Author",
                    ),
                    errors=[],
                )
            ]
            mock_google.return_value = FetchResult(
                isbn="9780306406157",
                record=SourceBookRecord(
                    source_name="google_books",
                    isbn="9780306406157",
                    editorial="Editorial",
                ),
                errors=[],
            )

            fetch_with_stages(
                [ISBNInput(isbn="9780306406157")],
                config,
                on_stage_update=on_stage_update,
            )

        assert on_stage_update.call_count >= 4
        assert any("initializing" in msg for msg in stage_updates)
        assert any("Open Library" in msg for msg in stage_updates)
        assert any("Google Books" in msg for msg in stage_updates)
        assert any("merging" in msg for msg in stage_updates)

    def test_on_fetch_start_and_complete_called(self) -> None:
        config = AppConfig(
            source_request_pause_seconds=0.0,
            open_library_batch_size=10,
            national_agency_routing_enabled=False,
        )
        on_fetch_start = MagicMock()
        on_fetch_complete = MagicMock()

        with (
            patch(
                "book_store_assistant.sources.staged.OpenLibrarySource.fetch_batch"
            ) as mock_batch,
            patch(
                "book_store_assistant.sources.staged.GoogleBooksSource.fetch"
            ) as mock_google,
        ):
            mock_batch.return_value = [
                FetchResult(
                    isbn="9780306406157",
                    record=SourceBookRecord(
                        source_name="open_library",
                        isbn="9780306406157",
                        title="Title",
                        author="Author",
                        editorial="Editorial",
                    ),
                    errors=[],
                )
            ]
            mock_google.return_value = FetchResult(
                isbn="9780306406157",
                record=None,
                errors=[],
            )

            fetch_with_stages(
                [ISBNInput(isbn="9780306406157")],
                config,
                on_fetch_start=on_fetch_start,
                on_fetch_complete=on_fetch_complete,
            )

        on_fetch_start.assert_called_once_with(1, 1, "9780306406157")
        on_fetch_complete.assert_called_once()
        args = on_fetch_complete.call_args
        assert args[0][0] == 1  # index
        assert args[0][1] == 1  # total
        assert isinstance(args[0][2], FetchResult)

    def test_callbacks_with_isbndb_enabled(self) -> None:
        """Verify stage update is called for ISBNdb stage when enabled."""
        config = AppConfig(
            source_request_pause_seconds=0.0,
            open_library_batch_size=10,
            isbndb_lookup_enabled=True,
            isbndb_api_key="test-key",
            national_agency_routing_enabled=False,
        )
        stage_updates: list[str] = []
        on_stage_update = MagicMock(side_effect=lambda msg: stage_updates.append(msg))

        with (
            patch(
                "book_store_assistant.sources.staged.ISBNdbSource.fetch"
            ) as mock_isbndb,
            patch(
                "book_store_assistant.sources.staged.OpenLibrarySource.fetch_batch"
            ) as mock_batch,
            patch(
                "book_store_assistant.sources.staged.GoogleBooksSource.fetch"
            ),
        ):
            mock_isbndb.return_value = FetchResult(
                isbn="9780306406157",
                record=SourceBookRecord(
                    source_name="isbndb",
                    isbn="9780306406157",
                    title="Title",
                    author="Author",
                    editorial="Editorial",
                ),
                errors=[],
                issue_codes=[],
            )
            mock_batch.return_value = []

            fetch_with_stages(
                [ISBNInput(isbn="9780306406157")],
                config,
                on_stage_update=on_stage_update,
            )

        assert any("ISBNdb" in msg for msg in stage_updates)

    def test_callbacks_with_national_stage(self) -> None:
        """Verify stage update is called for national agency stage."""
        config = AppConfig(
            source_request_pause_seconds=0.0,
            open_library_batch_size=10,
            national_agency_routing_enabled=True,
        )
        stage_updates: list[str] = []
        on_stage_update = MagicMock(side_effect=lambda msg: stage_updates.append(msg))

        national_source = _make_national_source_mock("9780306406157", title="National Title")

        with (
            patch(
                "book_store_assistant.sources.staged.get_national_source",
                return_value=national_source,
            ),
            patch(
                "book_store_assistant.sources.staged.OpenLibrarySource.fetch_batch"
            ) as mock_batch,
            patch(
                "book_store_assistant.sources.staged.GoogleBooksSource.fetch"
            ) as mock_google,
        ):
            mock_batch.return_value = [
                FetchResult(
                    isbn="9780306406157",
                    record=SourceBookRecord(
                        source_name="open_library",
                        isbn="9780306406157",
                        author="Author",
                    ),
                    errors=[],
                )
            ]
            mock_google.return_value = FetchResult(
                isbn="9780306406157",
                record=SourceBookRecord(
                    source_name="google_books",
                    isbn="9780306406157",
                    editorial="Editorial",
                ),
                errors=[],
            )

            fetch_with_stages(
                [ISBNInput(isbn="9780306406157")],
                config,
                on_stage_update=on_stage_update,
            )

        assert any("national" in msg.lower() for msg in stage_updates)
        assert any("bne" in msg.lower() for msg in stage_updates)


# ---------------------------------------------------------------------------
# Tests for multiple ISBN handling and Open Library batch merge
# ---------------------------------------------------------------------------


class TestFetchWithStagesMultipleISBNs:
    def test_handles_two_isbns_with_different_completeness(self) -> None:
        config = AppConfig(
            source_request_pause_seconds=0.0,
            open_library_batch_size=10,
            national_agency_routing_enabled=False,
        )

        isbn_complete = "9780306406157"
        isbn_incomplete = "9780451524935"

        with (
            patch(
                "book_store_assistant.sources.staged.OpenLibrarySource.fetch_batch"
            ) as mock_batch,
            patch(
                "book_store_assistant.sources.staged.GoogleBooksSource.fetch"
            ) as mock_google,
        ):
            mock_batch.return_value = [
                FetchResult(
                    isbn=isbn_complete,
                    record=SourceBookRecord(
                        source_name="open_library",
                        isbn=isbn_complete,
                        title="Title 1",
                        author="Author 1",
                        editorial="Editorial 1",
                    ),
                    errors=[],
                ),
                FetchResult(
                    isbn=isbn_incomplete,
                    record=SourceBookRecord(
                        source_name="open_library",
                        isbn=isbn_incomplete,
                        title="Title 2",
                    ),
                    errors=[],
                ),
            ]
            mock_google.return_value = FetchResult(
                isbn=isbn_incomplete,
                record=SourceBookRecord(
                    source_name="google_books",
                    isbn=isbn_incomplete,
                    author="Google Author 2",
                    editorial="Google Editorial 2",
                ),
                errors=[],
            )

            results = fetch_with_stages(
                [
                    ISBNInput(isbn=isbn_complete),
                    ISBNInput(isbn=isbn_incomplete),
                ],
                config,
            )

        assert len(results) == 2
        # First ISBN was complete after OL, so Google not called for it
        assert results[0].record is not None
        assert results[0].record.title == "Title 1"
        # Second ISBN needed Google for missing fields
        assert results[1].record is not None
        assert results[1].record.title == "Title 2"
        assert results[1].record.author == "Google Author 2"
