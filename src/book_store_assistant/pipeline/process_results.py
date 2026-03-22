from pydantic import BaseModel, Field

from book_store_assistant.pipeline.results import InputReadResult
from book_store_assistant.publisher_identity.models import PublisherIdentityResult
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.results import FetchResult


class ProcessResult(BaseModel):
    input_result: InputReadResult
    fetch_results: list[FetchResult]
    publisher_identity_results: list[PublisherIdentityResult] = Field(default_factory=list)
    resolution_results: list[ResolutionResult]
