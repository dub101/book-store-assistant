from typing import Protocol

from book_store_assistant.bibliographic.evidence import (
    WebSearchBibliographicExtraction,
    WebSearchEvidenceDocument,
)
from book_store_assistant.sources.models import SourceBookRecord


class BibliographicEvidenceExtractor(Protocol):
    def extract(
        self,
        source_record: SourceBookRecord,
        evidence_documents: list[WebSearchEvidenceDocument],
    ) -> WebSearchBibliographicExtraction | None:
        """Return grounded bibliographic extraction from trusted evidence."""
