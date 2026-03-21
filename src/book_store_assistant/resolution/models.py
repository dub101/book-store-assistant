from pydantic import BaseModel, Field


class RecordValidationAssessment(BaseModel):
    accepted: bool
    confidence: float = 0.0
    issues: list[str] = Field(default_factory=list)
    explanation: str | None = None
