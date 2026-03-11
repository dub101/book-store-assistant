from typing import Protocol

from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.subjects import SubjectEntry


class SubjectMapper(Protocol):
    def map_subject(
        self,
        record: SourceBookRecord,
        allowed_subject_entries: list[SubjectEntry],
    ) -> str | None:
        """Return a catalog subject description or None."""
