"""Tests for the provider factory functions."""

from unittest.mock import patch

from book_store_assistant.config import AIProvider, AppConfig
from book_store_assistant.resolution.openai_bibliographic_validator import (
    OpenAIBibliographicValidator,
)
from book_store_assistant.resolution.providers import (
    build_default_llm_enricher,
    build_default_record_quality_validator,
)
from book_store_assistant.sources.llm_enrichment import LLMWebEnricher


def _make_config(**overrides) -> AppConfig:
    """Build an AppConfig with sensible defaults for testing, bypassing env vars."""
    defaults = dict(
        llm_record_validation_enabled=True,
        llm_enrichment_enabled=True,
        ai_provider=AIProvider.OPENAI,
        openai_api_key="sk-test-key",
        openai_api_base_url="https://api.openai.com/v1",
        openai_model="gpt-4o-mini",
        request_timeout_seconds=10.0,
        llm_record_validation_min_confidence=0.8,
        llm_enrichment_timeout_seconds=60.0,
    )
    defaults.update(overrides)
    return AppConfig(**defaults)


# ---------------------------------------------------------------------------
# build_default_record_quality_validator
# ---------------------------------------------------------------------------


class TestBuildDefaultRecordQualityValidator:
    def test_returns_validator_when_enabled_with_api_key(self) -> None:
        config = _make_config(
            llm_record_validation_enabled=True,
            openai_api_key="sk-real-key",
        )
        result = build_default_record_quality_validator(config)

        assert result is not None
        assert isinstance(result, OpenAIBibliographicValidator)
        assert result.api_key == "sk-real-key"

    def test_returns_none_when_validation_disabled(self) -> None:
        config = _make_config(llm_record_validation_enabled=False)
        result = build_default_record_quality_validator(config)

        assert result is None

    def test_returns_none_when_no_api_key(self) -> None:
        config = _make_config(
            llm_record_validation_enabled=True,
            openai_api_key=None,
        )
        result = build_default_record_quality_validator(config)

        assert result is None

    def test_passes_config_values_to_validator(self) -> None:
        config = _make_config(
            openai_api_key="sk-custom",
            openai_api_base_url="https://custom.api.com/v1",
            openai_model="gpt-4o",
            request_timeout_seconds=30.0,
            llm_record_validation_min_confidence=0.9,
        )
        result = build_default_record_quality_validator(config)

        assert isinstance(result, OpenAIBibliographicValidator)
        assert result.api_key == "sk-custom"
        assert result.base_url == "https://custom.api.com/v1"
        assert result.model == "gpt-4o"
        assert result.timeout_seconds == 30.0
        assert result.min_confidence == 0.9


# ---------------------------------------------------------------------------
# build_default_llm_enricher
# ---------------------------------------------------------------------------


class TestBuildDefaultLlmEnricher:
    @patch(
        "book_store_assistant.sources.llm_enrichment._load_subject_catalog",
        return_value=[],
    )
    def test_returns_enricher_when_enabled_with_api_key(self, _mock_catalog) -> None:
        config = _make_config(
            llm_enrichment_enabled=True,
            openai_api_key="sk-enricher-key",
        )
        result = build_default_llm_enricher(config)

        assert result is not None
        assert isinstance(result, LLMWebEnricher)

    def test_returns_none_when_enrichment_disabled(self) -> None:
        config = _make_config(llm_enrichment_enabled=False)
        result = build_default_llm_enricher(config)

        assert result is None

    @patch(
        "book_store_assistant.sources.llm_enrichment._load_subject_catalog",
        return_value=[],
    )
    def test_returns_none_when_no_api_key(self, _mock_catalog) -> None:
        config = _make_config(
            llm_enrichment_enabled=True,
            openai_api_key=None,
        )
        result = build_default_llm_enricher(config)

        assert result is None
