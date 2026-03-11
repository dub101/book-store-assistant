import os
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    RULES_ONLY = "rules-only"
    AI_ENRICHED = "ai-enriched"


class AIProvider(str, Enum):
    OPENAI = "openai"


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return float(raw_value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    return default


def _env_execution_mode() -> ExecutionMode:
    raw_value = os.getenv("BSA_EXECUTION_MODE")
    if raw_value is None:
        return ExecutionMode.RULES_ONLY

    try:
        return ExecutionMode(raw_value)
    except ValueError:
        return ExecutionMode.RULES_ONLY


class AppConfig(BaseModel):
    input_dir: Path = Path("data/input")
    output_dir: Path = Path("data/output")
    intermediate_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("BSA_INTERMEDIATE_DIR", "data/intermediate"))
    )
    source_cache_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("BSA_SOURCE_CACHE_DIR", "data/cache/fetch"))
    )
    source_cache_enabled: bool = Field(
        default_factory=lambda: _env_bool("BSA_SOURCE_CACHE_ENABLED", True)
    )
    source_request_pause_seconds: float = Field(
        default_factory=lambda: _env_float("BSA_SOURCE_REQUEST_PAUSE_SECONDS", 0.5)
    )
    open_library_batch_size: int = Field(
        default_factory=lambda: _env_int("BSA_OPEN_LIBRARY_BATCH_SIZE", 25)
    )
    google_books_api_base_url: str = "https://www.googleapis.com/books/v1/volumes"
    google_books_max_retries: int = Field(
        default_factory=lambda: _env_int("BSA_GOOGLE_BOOKS_MAX_RETRIES", 2)
    )
    google_books_backoff_seconds: float = Field(
        default_factory=lambda: _env_float("BSA_GOOGLE_BOOKS_BACKOFF_SECONDS", 1.0)
    )
    open_library_api_base_url: str = "https://openlibrary.org/api/books"
    publisher_page_lookup_enabled: bool = Field(
        default_factory=lambda: _env_bool("BSA_PUBLISHER_PAGE_LOOKUP_ENABLED", False)
    )
    request_timeout_seconds: float = Field(
        default_factory=lambda: _env_float("BSA_REQUEST_TIMEOUT_SECONDS", 10.0)
    )
    execution_mode: ExecutionMode = Field(default_factory=_env_execution_mode)
    llm_subject_mapping_enabled: bool = Field(
        default_factory=lambda: _env_bool("BSA_LLM_SUBJECT_MAPPING_ENABLED", True)
    )
    llm_subject_mapping_min_confidence: float = Field(
        default_factory=lambda: _env_float("BSA_LLM_SUBJECT_MAPPING_MIN_CONFIDENCE", 0.85)
    )
    ai_provider: AIProvider = AIProvider.OPENAI
    openai_api_key: str | None = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    openai_api_base_url: str = Field(
        default_factory=lambda: os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1")
    )
    openai_model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
