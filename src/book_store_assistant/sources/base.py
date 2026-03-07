from typing import Protocol

from book_store_assistant.models import BookRecord


class MetadataSource(Protocol):
    def fetch(self, isbn: str) -> BookRecord | None:
        """Return metadata for an ISBN when the source can resolve it."""
