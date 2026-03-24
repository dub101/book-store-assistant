from typing import Any

from pydantic import BaseModel, Field

from book_store_assistant.publisher_identity.models import PublisherIdentityResult
from book_store_assistant.sources.models import SourceBookRecord


class FetchResult(BaseModel):
    isbn: str
    record: SourceBookRecord | None
    errors: list[str]
    issue_codes: list[str] = Field(default_factory=list)
    publisher_identity: PublisherIdentityResult | None = None
    raw_payload: str | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
