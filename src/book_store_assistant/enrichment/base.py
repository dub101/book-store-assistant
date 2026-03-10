from typing import Protocol

from book_store_assistant.enrichment.models import EnrichmentResult
from book_store_assistant.sources.models import SourceBookRecord


class SourceRecordEnricher(Protocol):
    def enrich(self, record: SourceBookRecord) -> EnrichmentResult:
        """Return enrichment data derived from a source record."""
