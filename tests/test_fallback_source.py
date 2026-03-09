import pytest

from book_store_assistant.sources.fallback import FallbackMetadataSource
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


class MissingSource:
    source_name = "missing_source"

    def __init__(self, errors: list[str] | str) -> None:
        if isinstance(errors, str):
            self.errors = [errors]
        else:
            self.errors = errors

    def fetch(self, isbn: str) -> FetchResult:
        return FetchResult(isbn=isbn, record=None, errors=self.errors)


class FoundSource:
    source_name = "found_source"

    def fetch(self, isbn: str) -> FetchResult:
        return FetchResult(
            isbn=isbn,
            record=SourceBookRecord(
                source_name="found_source",
                isbn=isbn,
                title="Example Title",
            ),
            errors=[],
        )


class StaticRecordSource:
    def __init__(self, source_name: str, record: SourceBookRecord) -> None:
        self.source_name = source_name
        self.record = record

    def fetch(self, isbn: str) -> FetchResult:
        return FetchResult(isbn=isbn, record=self.record, errors=[])


def test_fallback_metadata_source_requires_at_least_one_source() -> None:
    with pytest.raises(ValueError, match="at least one source"):
        FallbackMetadataSource([])


def test_fallback_metadata_source_returns_successful_result() -> None:
    source = FallbackMetadataSource(
        [
            MissingSource("No Google Books match found."),
            FoundSource(),
        ]
    )

    result = source.fetch("9780306406157")

    assert result.record is not None
    assert result.record.source_name == "found_source"
    assert result.errors == []


def test_fallback_metadata_source_accumulates_errors_when_all_sources_fail() -> None:
    source = FallbackMetadataSource(
        [
            MissingSource("No Google Books match found."),
            MissingSource("No Open Library match found."),
        ]
    )

    result = source.fetch("9780306406157")

    assert result.record is None
    assert result.errors == [
        "missing_source: No Google Books match found.",
        "missing_source: No Open Library match found.",
    ]


def test_fallback_metadata_source_deduplicates_prefixed_errors() -> None:
    source = FallbackMetadataSource(
        [
            MissingSource(["Timeout", "Timeout"]),
            MissingSource(["Timeout"]),
        ]
    )

    result = source.fetch("9780306406157")

    assert result.record is None
    assert result.errors == ["missing_source: Timeout"]


def test_fallback_metadata_source_merges_missing_fields_from_later_sources() -> None:
    source = FallbackMetadataSource(
        [
            StaticRecordSource(
                "google_books",
                SourceBookRecord(
                    source_name="google_books",
                    isbn="9780306406157",
                    title="Example Title",
                    author="Primary Author",
                    categories=["Fiction"],
                ),
            ),
            StaticRecordSource(
                "open_library",
                SourceBookRecord(
                    source_name="open_library",
                    isbn="9780306406157",
                    editorial="Later Editorial",
                    synopsis="Sinopsis en espanol.",
                    subject="Novela",
                    categories=["fiction", "Drama"],
                    language="es",
                ),
            ),
        ]
    )

    result = source.fetch("9780306406157")

    assert result.record is not None
    assert result.record.source_name == "google_books + open_library"
    assert result.record.title == "Example Title"
    assert result.record.author == "Primary Author"
    assert result.record.editorial == "Later Editorial"
    assert result.record.synopsis == "Sinopsis en espanol."
    assert result.record.subject == "Novela"
    assert result.record.language == "es"
    assert result.record.categories == ["Fiction", "Drama"]


def test_fallback_metadata_source_does_not_override_existing_values() -> None:
    source = FallbackMetadataSource(
        [
            StaticRecordSource(
                "google_books",
                SourceBookRecord(
                    source_name="google_books",
                    isbn="9780306406157",
                    title="Primary Title",
                    author="Primary Author",
                    editorial="Primary Editorial",
                    synopsis="Sinopsis primaria.",
                    subject="Historia",
                    language="es",
                ),
            ),
            StaticRecordSource(
                "open_library",
                SourceBookRecord(
                    source_name="open_library",
                    isbn="9780306406157",
                    title="Secondary Title",
                    author="Secondary Author",
                    editorial="Secondary Editorial",
                    synopsis="Sinopsis secundaria.",
                    subject="Novela",
                    language="en",
                ),
            ),
        ]
    )

    result = source.fetch("9780306406157")

    assert result.record is not None
    assert result.record.title == "Primary Title"
    assert result.record.author == "Primary Author"
    assert result.record.editorial == "Primary Editorial"
    assert result.record.synopsis == "Sinopsis primaria."
    assert result.record.subject == "Historia"
    assert result.record.language == "es"
