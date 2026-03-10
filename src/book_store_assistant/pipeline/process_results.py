from pydantic import BaseModel, Field

from book_store_assistant.enrichment.models import EnrichmentResult
from book_store_assistant.pipeline.results import InputReadResult
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.results import FetchResult


class ProcessResult(BaseModel):
    input_result: InputReadResult
    fetch_results: list[FetchResult]
    enrichment_results: list[EnrichmentResult] = Field(default_factory=list)
    resolution_results: list[ResolutionResult]
