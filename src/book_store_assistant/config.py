import os
import sys
import tomllib
from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


class AIProvider(str, Enum):
    OPENAI = "openai"


def _default_config_path() -> Path:
    override = os.getenv("BSA_CONFIG_FILE")
    if override:
        return Path(override)
    # When bundled by PyInstaller, sys.frozen is set and sys.executable points
    # to the .exe. Resolve bsa.toml next to the executable so double-clicking
    # from any working directory still finds the shipped config.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "bsa.toml"
    return Path("bsa.toml")


@lru_cache(maxsize=1)
def _load_config_file() -> dict[str, object]:
    config_path = _default_config_path()
    if not config_path.exists():
        return {}

    try:
        with config_path.open("rb") as config_file:
            payload = tomllib.load(config_file)
    except (OSError, tomllib.TOMLDecodeError):
        return {}

    return payload


def _config_value(name: str, default: object) -> object:
    return _load_config_file().get(name, default)


def _secret_from_env_or_file(env_name: str, file_key: str) -> str | None:
    raw_value = os.getenv(env_name)
    if raw_value:
        return raw_value
    file_value = _config_value(file_key, None)
    if isinstance(file_value, str) and file_value:
        return file_value
    return None


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


class AppConfig(BaseModel):
    source_request_pause_seconds: float = Field(
        default_factory=lambda: _env_float("BSA_SOURCE_REQUEST_PAUSE_SECONDS", 0.5)
    )
    open_library_batch_size: int = Field(
        default_factory=lambda: _env_int("BSA_OPEN_LIBRARY_BATCH_SIZE", 25)
    )
    bne_lookup_enabled: bool = Field(
        default_factory=lambda: _env_bool("BSA_BNE_LOOKUP_ENABLED", True)
    )
    national_agency_routing_enabled: bool = Field(
        default_factory=lambda: _env_bool("BSA_NATIONAL_AGENCY_ROUTING_ENABLED", True)
    )
    bne_sru_base_url: str = Field(
        default_factory=lambda: _configured_str(
            "bne_sru_base_url",
            "https://catalogo.bne.es/view/sru/34BNE_INST",
        )
    )
    isbndb_api_key: str | None = Field(
        default_factory=lambda: _secret_from_env_or_file("ISBNDB_API_KEY", "isbndb_api_key")
    )
    isbndb_lookup_enabled: bool = Field(
        default_factory=lambda: _env_bool("BSA_ISBNDB_LOOKUP_ENABLED", True)
    )
    google_books_api_base_url: str = "https://www.googleapis.com/books/v1/volumes"
    google_books_max_retries: int = Field(
        default_factory=lambda: _env_int("BSA_GOOGLE_BOOKS_MAX_RETRIES", 2)
    )
    google_books_backoff_seconds: float = Field(
        default_factory=lambda: _env_float("BSA_GOOGLE_BOOKS_BACKOFF_SECONDS", 1.0)
    )
    open_library_api_base_url: str = "https://openlibrary.org/api/books"
    request_timeout_seconds: float = Field(
        default_factory=lambda: _env_float("BSA_REQUEST_TIMEOUT_SECONDS", 10.0)
    )
    llm_record_validation_enabled: bool = Field(
        default_factory=lambda: _env_bool("BSA_LLM_RECORD_VALIDATION_ENABLED", True)
    )
    llm_record_validation_min_confidence: float = Field(
        default_factory=lambda: _env_float("BSA_LLM_RECORD_VALIDATION_MIN_CONFIDENCE", 0.8)
    )
    llm_enrichment_enabled: bool = Field(
        default_factory=lambda: _env_bool("BSA_LLM_ENRICHMENT_ENABLED", True)
    )
    llm_enrichment_timeout_seconds: float = Field(
        default_factory=lambda: _env_float("BSA_LLM_ENRICHMENT_TIMEOUT_SECONDS", 60.0)
    )
    ai_provider: AIProvider = AIProvider.OPENAI
    openai_api_key: str | None = Field(
        default_factory=lambda: _secret_from_env_or_file("OPENAI_API_KEY", "openai_api_key")
    )
    openai_api_base_url: str = Field(
        default_factory=lambda: os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1")
    )
    openai_model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
