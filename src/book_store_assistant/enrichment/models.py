from pydantic import BaseModel, Field


class DescriptiveEvidence(BaseModel):
    source_name: str
    evidence_type: str
    evidence_origin: str
    text: str
    source_url: str | None = None
    language: str | None = None
    extraction_method: str | None = None
    quality_flags: list[str] = Field(default_factory=list)


class GeneratedSynopsis(BaseModel):
    text: str
    language: str = "es"
    evidence_indexes: list[int] = Field(default_factory=list)
    validation_flags: list[str] = Field(default_factory=list)
    raw_output_text: str | None = None


class EnrichmentResult(BaseModel):
    isbn: str
    source_name: str | None = None
    applied: bool = False
    skipped_reason: str | None = None
    evidence: list[DescriptiveEvidence] = Field(default_factory=list)
    generated_synopsis: GeneratedSynopsis | None = None
    errors: list[str] = Field(default_factory=list)
