from pydantic import BaseModel, Field, HttpUrl


class SourceBookRecord(BaseModel):
    source_name: str
    isbn: str
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
