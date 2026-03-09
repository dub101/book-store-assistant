from pydantic import BaseModel, Field

from book_store_assistant.models import BookRecord
from book_store_assistant.sources.models import SourceBookRecord


class ResolutionResult(BaseModel):
    record: BookRecord | None
    source_record: SourceBookRecord | None
    errors: list[str]
    reason_codes: list[str] = Field(default_factory=list)
    review_details: list[str] = Field(default_factory=list)
