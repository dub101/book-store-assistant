import os
import tomllib
from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    RULES_ONLY = "rules-only"
    AI_ENRICHED = "ai-enriched"


class AIProvider(str, Enum):
    OPENAI = "openai"


@lru_cache(maxsize=1)
def _load_config_file() -> dict[str, object]:
    config_path = Path(os.getenv("BSA_CONFIG_FILE", "bsa.toml"))
    if not config_path.exists():
        return {}

    try:
        with config_path.open("rb") as config_file:
            payload = tomllib.load(config_file)
    except (OSError, tomllib.TOMLDecodeError):
        return {}

    return payload


def clear_config_file_cache() -> None:
    _load_config_file.cache_clear()


def _config_value(name: str, default: object) -> object:
    return _load_config_file().get(name, default)


def _configured_str(name: str, default: str) -> str:
    env_name = f"BSA_{name.upper()}"
    raw_value = os.getenv(env_name)
    if raw_value is not None:
        return raw_value

    file_value = _config_value(name, default)
    return file_value if isinstance(file_value, str) else default


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        file_key = name.removeprefix("BSA_").casefold()
        file_value = _config_value(file_key, default)
        if isinstance(file_value, (int, float)):
            return float(file_value)
        return default

    try:
        return float(raw_value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        file_key = name.removeprefix("BSA_").casefold()
        file_value = _config_value(file_key, default)
        if isinstance(file_value, int):
            return file_value
        return default

    try:
        return int(raw_value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        file_key = name.removeprefix("BSA_").casefold()
        file_value = _config_value(file_key, default)
        if isinstance(file_value, bool):
            return file_value
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
        file_value = _config_value("execution_mode", ExecutionMode.RULES_ONLY.value)
        if isinstance(file_value, str):
            try:
                return ExecutionMode(file_value)
            except ValueError:
                return ExecutionMode.RULES_ONLY
        return ExecutionMode.RULES_ONLY

    try:
        return ExecutionMode(raw_value)
    except ValueError:
        return ExecutionMode.RULES_ONLY


class AppConfig(BaseModel):
    input_dir: Path = Field(
        default_factory=lambda: Path(_configured_str("input_dir", "data/input"))
    )
    output_dir: Path = Field(
        default_factory=lambda: Path(_configured_str("output_dir", "data/output"))
    )
    intermediate_dir: Path = Field(
        default_factory=lambda: Path(_configured_str("intermediate_dir", "data/intermediate"))
    )
    source_cache_dir: Path = Field(
        default_factory=lambda: Path(_configured_str("source_cache_dir", "data/cache/fetch"))
    )
    source_cache_enabled: bool = Field(
        default_factory=lambda: _env_bool("BSA_SOURCE_CACHE_ENABLED", True)
    )
    publisher_page_cache_dir: Path = Field(
        default_factory=lambda: Path(
            _configured_str("publisher_page_cache_dir", "data/cache/publisher_pages")
        )
    )
    publisher_page_cache_enabled: bool = Field(
        default_factory=lambda: _env_bool("BSA_PUBLISHER_PAGE_CACHE_ENABLED", True)
    )
    source_request_pause_seconds: float = Field(
        default_factory=lambda: _env_float("BSA_SOURCE_REQUEST_PAUSE_SECONDS", 0.5)
    )
    open_library_batch_size: int = Field(
        default_factory=lambda: _env_int("BSA_OPEN_LIBRARY_BATCH_SIZE", 25)
    )
    bne_lookup_enabled: bool = Field(
        default_factory=lambda: _env_bool("BSA_BNE_LOOKUP_ENABLED", True)
    )
    bne_sru_base_url: str = Field(
        default_factory=lambda: _configured_str(
            "bne_sru_base_url",
            "https://catalogo.bne.es/view/sru/34BNE_INST",
        )
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
    publisher_page_timeout_seconds: float = Field(
        default_factory=lambda: _env_float("BSA_PUBLISHER_PAGE_TIMEOUT_SECONDS", 3.0)
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
