from pydantic import BaseModel

from book_store_assistant.pipeline.results import InputReadResult
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.results import FetchResult


class ProcessResult(BaseModel):
    input_result: InputReadResult
    fetch_results: list[FetchResult]
    resolution_results: list[ResolutionResult]
