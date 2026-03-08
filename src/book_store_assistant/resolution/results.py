from pydantic import BaseModel

from book_store_assistant.models import BookRecord
from book_store_assistant.sources.models import SourceBookRecord


class ResolutionResult(BaseModel):
    record: BookRecord | None
    source_record: SourceBookRecord
    errors: list[str]
