from pydantic import BaseModel, Field


class PublisherIdentityResult(BaseModel):
    isbn: str
    publisher_name: str | None = None
    imprint_name: str | None = None
    publisher_group_key: str | None = None
    source_name: str | None = None
    source_field: str | None = None
    confidence: float = 0.0
    resolution_method: str | None = None
    evidence: list[str] = Field(default_factory=list)
