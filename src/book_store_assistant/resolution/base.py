from typing import Protocol

from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.models import RecordValidationAssessment
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.subjects import SubjectEntry


class SubjectMapper(Protocol):
    def map_subject(
        self,
        record: SourceBookRecord,
        allowed_subject_entries: list[SubjectEntry],
    ) -> str | None:
        """Return a catalog subject description or None."""


class RecordQualityValidator(Protocol):
    def validate(
        self,
        source_record: SourceBookRecord,
        candidate_record: BookRecord | BibliographicRecord,
    ) -> RecordValidationAssessment | None:
        """Return a validation assessment or None when validation cannot be completed."""
