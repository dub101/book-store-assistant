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


def test_fallback_metadata_source_requires_at_least_one_source() -> None:
    with pytest.raises(ValueError, match="at least one source"):
        FallbackMetadataSource([])


def test_fallback_metadata_source_returns_first_successful_result() -> None:
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
