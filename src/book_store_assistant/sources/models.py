from pydantic import BaseModel, Field, HttpUrl


class FieldCandidate(BaseModel):
    field_name: str
    value: str
    source_name: str
    confidence: float = 0.0
    language: str | None = None
    source_url: HttpUrl | None = None
    extraction_method: str | None = None


class SourceBookRecord(BaseModel):
    source_name: str
    isbn: str
    source_url: HttpUrl | None = None
    raw_source_payload: str | None = None
    title: str | None = None
    subtitle: str | None = None
    author: str | None = None
    editorial: str | None = None
    synopsis: str | None = None
    subject: str | None = None
    categories: list[str] = Field(default_factory=list)
    cover_url: HttpUrl | None = None
    language: str | None = None
    field_sources: dict[str, str] = Field(default_factory=dict)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    field_candidates: dict[str, list[FieldCandidate]] = Field(default_factory=dict)
