from typing import Protocol

from book_store_assistant.sources.results import FetchResult


class MetadataSource(Protocol):
    def fetch(self, isbn: str) -> FetchResult:
        """Return fetch metadata for an ISBN."""
