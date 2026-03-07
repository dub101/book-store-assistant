from pydantic import BaseModel, HttpUrl


class BookRecord(BaseModel):
    isbn: str
    title: str
    subtitle: str | None = None
    author: str
    editorial: str
    synopsis: str
    subject: str
    cover_url: HttpUrl | None = None
