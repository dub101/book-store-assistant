from pydantic import BaseModel

from book_store_assistant.pipeline.contracts import ISBNInput


class InputReadResult(BaseModel):
    valid_inputs: list[ISBNInput]
    invalid_values: list[str]
    duplicate_count: int = 0
