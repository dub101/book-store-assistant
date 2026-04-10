from typing import Any

from pydantic import BaseModel, Field

from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.resolution.models import RecordValidationAssessment
from book_store_assistant.sources.models import SourceBookRecord


class ResolutionResult(BaseModel):
    record: BibliographicRecord | None
    candidate_record: BibliographicRecord | None = None
    source_record: SourceBookRecord | None
    validation_assessment: RecordValidationAssessment | None = None
    errors: list[str]
    reason_codes: list[str] = Field(default_factory=list)
    review_details: list[str] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    path_summary: dict[str, Any] = Field(default_factory=dict)
