from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class ExecutionMode(str, Enum):
    RULES_ONLY = "rules-only"
    AI_ENRICHED = "ai-enriched"


class AppConfig(BaseModel):
    input_dir: Path = Path("data/input")
    output_dir: Path = Path("data/output")
    google_books_api_base_url: str = "https://www.googleapis.com/books/v1/volumes"
    open_library_api_base_url: str = "https://openlibrary.org/api/books"
    request_timeout_seconds: float = 10.0
    execution_mode: ExecutionMode = ExecutionMode.RULES_ONLY
