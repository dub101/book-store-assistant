from pydantic import BaseModel


class ISBNInput(BaseModel):
    isbn: str
