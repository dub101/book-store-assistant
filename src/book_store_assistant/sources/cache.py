from pathlib import Path

from pydantic import BaseModel

from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.results import FetchResult

CACHE_VERSION = 1


class CachedFetchResult(BaseModel):
    version: int = CACHE_VERSION
    source_key: str
    result: FetchResult


class FetchResultCache:
    def __init__(self, cache_dir: Path, source_key: str) -> None:
        self.cache_dir = cache_dir
        self.source_key = source_key

    def _cache_path(self, isbn: str) -> Path:
        return self.cache_dir / f"{isbn}.json"

    def get(self, isbn: str) -> FetchResult | None:
        cache_path = self._cache_path(isbn)
        if not cache_path.exists():
            return None

        try:
            cached = CachedFetchResult.model_validate_json(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

        if cached.version != CACHE_VERSION or cached.source_key != self.source_key:
            return None

        return cached.result

    def set(self, result: FetchResult) -> None:
        if result.record is None:
            return

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self._cache_path(result.isbn)
        cached = CachedFetchResult(source_key=self.source_key, result=result)
        cache_path.write_text(cached.model_dump_json(indent=2), encoding="utf-8")


class CachedMetadataSource:
    def __init__(
        self,
        source: MetadataSource,
        cache_dir: Path,
        source_key: str,
    ) -> None:
        self.source = source
        self.source_key = source_key
        self.cache = FetchResultCache(cache_dir, source_key)

    def fetch(self, isbn: str) -> FetchResult:
        cached_result = self.cache.get(isbn)
        if cached_result is not None:
            return cached_result

        result = self.source.fetch(isbn)
        self.cache.set(result)
        return result
