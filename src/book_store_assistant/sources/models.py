from pydantic import BaseModel, HttpUrl


class SourceBookRecord(BaseModel):
    source_name: str
    isbn: str
    title: str | None = None
    subtitle: str | None = None
    author: str | None = None
    editorial: str | None = None
    synopsis: str | None = None
    subject: str | None = None
    cover_url: HttpUrl | None = None
    language: str | None = None
