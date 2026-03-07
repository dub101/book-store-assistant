from typing import Protocol

from book_store_assistant.models import BookRecord


class BookEnricher(Protocol):
    def enrich(self, record: BookRecord) -> BookRecord:
        """Return an enriched version of a book record."""
