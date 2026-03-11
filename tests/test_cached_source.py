from pathlib import Path

from book_store_assistant.sources.cache import CachedMetadataSource
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


class CountingSource:
    def __init__(self, result: FetchResult) -> None:
        self.result = result
        self.calls = 0

    def fetch(self, isbn: str) -> FetchResult:
        self.calls += 1
        return self.result.model_copy(update={"isbn": isbn})


def test_cached_metadata_source_returns_cached_success_without_refetching(
    tmp_path: Path,
) -> None:
    source = CountingSource(
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Example Title",
            ),
            errors=[],
        )
    )
    cached_source = CachedMetadataSource(
        source=source,
        cache_dir=tmp_path / "cache",
        source_key="test_source",
    )

    first = cached_source.fetch("9780306406157")
    second = cached_source.fetch("9780306406157")

    assert first == second
    assert source.calls == 1


def test_cached_metadata_source_persists_successful_fetch_results(tmp_path: Path) -> None:
    source = CountingSource(
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="open_library",
                isbn="9780306406157",
                title="Recovered Title",
            ),
            errors=["google_books: Timeout"],
            issue_codes=["GOOGLE_BOOKS:GOOGLE_BOOKS_TIMEOUT"],
        )
    )
    cache_dir = tmp_path / "cache"
    cached_source = CachedMetadataSource(
        source=source,
        cache_dir=cache_dir,
        source_key="default_metadata_sources_v1",
    )

    result = cached_source.fetch("9780306406157")

    assert result.record is not None
    assert (cache_dir / "9780306406157.json").exists()


def test_cached_metadata_source_does_not_persist_failed_fetch_results(tmp_path: Path) -> None:
    source = CountingSource(
        FetchResult(
            isbn="9780306406157",
            record=None,
            errors=["google_books: 429 Too Many Requests"],
            issue_codes=["GOOGLE_BOOKS:GOOGLE_BOOKS_RATE_LIMITED"],
        )
    )
    cache_dir = tmp_path / "cache"
    cached_source = CachedMetadataSource(
        source=source,
        cache_dir=cache_dir,
        source_key="default_metadata_sources_v1",
    )

    first = cached_source.fetch("9780306406157")
    second = cached_source.fetch("9780306406157")

    assert first.record is None
    assert second.record is None
    assert source.calls == 2
    assert not (cache_dir / "9780306406157.json").exists()
