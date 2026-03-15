import time
from pathlib import Path

from pydantic import BaseModel, Field

from book_store_assistant.sources.results import FetchResult

CACHE_VERSION = 2


class CachedFetchResult(BaseModel):
    version: int = CACHE_VERSION
    source_key: str
    result: FetchResult
    cached_at: float = Field(default_factory=time.time)


class FetchResultCache:
    def __init__(self, cache_dir: Path, source_key: str) -> None:
        self.cache_dir = cache_dir
        self.source_key = source_key

    def _cache_path(self, isbn: str) -> Path:
        return self.cache_dir / f"{isbn}.json"

    def get_entry(self, isbn: str) -> CachedFetchResult | None:
        cache_path = self._cache_path(isbn)
        if not cache_path.exists():
            return None

        try:
            cached = CachedFetchResult.model_validate_json(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

        if cached.version != CACHE_VERSION or cached.source_key != self.source_key:
            return None

        return cached

    def get(self, isbn: str, max_age_seconds: float | None = None) -> FetchResult | None:
        cached = self.get_entry(isbn)
        if cached is None:
            return None
        if max_age_seconds is not None and max_age_seconds >= 0:
            if time.time() - cached.cached_at > max_age_seconds:
                return None

        return cached.result

    def set(self, result: FetchResult, allow_empty: bool = False) -> None:
        if result.record is None and not allow_empty:
            return

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self._cache_path(result.isbn)
        cached = CachedFetchResult(source_key=self.source_key, result=result)
        cache_path.write_text(cached.model_dump_json(indent=2), encoding="utf-8")
