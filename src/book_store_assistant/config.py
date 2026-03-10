import os
from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class ExecutionMode(str, Enum):
    RULES_ONLY = "rules-only"
    AI_ENRICHED = "ai-enriched"


class AIProvider(str, Enum):
    OPENAI = "openai"


class AppConfig(BaseModel):
    input_dir: Path = Path("data/input")
    output_dir: Path = Path("data/output")
    google_books_api_base_url: str = "https://www.googleapis.com/books/v1/volumes"
    google_books_max_retries: int = 2
    google_books_backoff_seconds: float = 1.0
    open_library_api_base_url: str = "https://openlibrary.org/api/books"
    request_timeout_seconds: float = 10.0
    execution_mode: ExecutionMode = ExecutionMode.RULES_ONLY
    ai_provider: AIProvider = AIProvider.OPENAI
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_api_base_url: str = os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
