from pydantic import BaseModel, Field, HttpUrl


class WebSearchEvidenceDocument(BaseModel):
    index: int
    url: HttpUrl
    domain: str
    page_title: str | None = None
    excerpt: str
    isbn_present: bool = True


class WebSearchBibliographicExtraction(BaseModel):
    confidence: float
    title: str | None = None
    subtitle: str | None = None
    author: str | None = None
    editorial: str | None = None
    publisher: str | None = None
    support: dict[str, list[int]] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    explanation: str | None = None
    raw_output_text: str | None = None
