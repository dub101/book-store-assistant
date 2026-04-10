from pydantic import BaseModel, HttpUrl


class BibliographicRecord(BaseModel):
    isbn: str
    title: str
    subtitle: str | None = None
    author: str
    editorial: str
    synopsis: str | None = None
    subject: str | None = None
    subject_code: str | None = None
    cover_url: HttpUrl | None = None
