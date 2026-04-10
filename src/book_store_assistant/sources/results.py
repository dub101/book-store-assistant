from typing import Any

from pydantic import BaseModel, Field

from book_store_assistant.sources.models import SourceBookRecord


class FetchResult(BaseModel):
    isbn: str
    record: SourceBookRecord | None
    errors: list[str]
    issue_codes: list[str] = Field(default_factory=list)
    raw_payload: str | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
