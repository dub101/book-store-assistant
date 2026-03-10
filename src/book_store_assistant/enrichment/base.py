from typing import Protocol

from book_store_assistant.enrichment.models import (
    DescriptiveEvidence,
    EnrichmentResult,
    GeneratedSynopsis,
)
from book_store_assistant.sources.models import SourceBookRecord


class SourceRecordEnricher(Protocol):
    def enrich(self, record: SourceBookRecord) -> EnrichmentResult:
        """Return enrichment data derived from a source record."""


class SynopsisGenerator(Protocol):
    def generate(
        self,
        isbn: str,
        evidence: list[DescriptiveEvidence],
    ) -> GeneratedSynopsis | None:
        """Return a grounded generated synopsis or None when no output is available."""


class PageContentFetcher(Protocol):
    def fetch_text(self, url: str) -> str | None:
        """Return fetched page text for a trusted source URL."""
