from pydantic import BaseModel


class BibliographicRecord(BaseModel):
    isbn: str
    title: str
    subtitle: str | None = None
    author: str
    editorial: str
    publisher: str
