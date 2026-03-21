from pydantic import BaseModel, Field


class RecordValidationAssessment(BaseModel):
    accepted: bool
    confidence: float = 0.0
    issues: list[str] = Field(default_factory=list)
    explanation: str | None = None


class SelectedFieldValues(BaseModel):
    title: str | None = None
    author: str | None = None
    editorial: str | None = None
    supporting_indexes: dict[str, int] = Field(default_factory=dict)
