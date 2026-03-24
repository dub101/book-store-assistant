from typing import Protocol

from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.publisher_identity.models import PublisherIdentityResult
from book_store_assistant.resolution.models import RecordValidationAssessment
from book_store_assistant.sources.models import SourceBookRecord


class RecordQualityValidator(Protocol):
    def validate(
        self,
        source_record: SourceBookRecord,
        candidate_record: BibliographicRecord,
        publisher_identity: PublisherIdentityResult | None = None,
    ) -> RecordValidationAssessment | None:
        """Return a validation assessment or None when validation cannot be completed."""
