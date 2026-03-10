from pydantic import BaseModel

from book_store_assistant.sources.models import SourceBookRecord


class FetchResult(BaseModel):
    isbn: str
    record: SourceBookRecord | None
    errors: list[str]
    issue_codes: list[str] = []
