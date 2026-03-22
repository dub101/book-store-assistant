from pydantic import BaseModel, Field

from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.publisher_identity.models import PublisherIdentityResult
from book_store_assistant.resolution.models import RecordValidationAssessment
from book_store_assistant.sources.models import SourceBookRecord


class ResolutionResult(BaseModel):
    record: BibliographicRecord | None
    candidate_record: BibliographicRecord | None = None
    source_record: SourceBookRecord | None
    publisher_identity: PublisherIdentityResult | None = None
    validation_assessment: RecordValidationAssessment | None = None
    errors: list[str]
    source_issue_codes: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    review_details: list[str] = Field(default_factory=list)
