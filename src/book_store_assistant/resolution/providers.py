from book_store_assistant.config import AIProvider, AppConfig
from book_store_assistant.resolution.base import RecordQualityValidator
from book_store_assistant.resolution.openai_bibliographic_validator import (
    OpenAIBibliographicValidator,
)
from book_store_assistant.sources.llm_enrichment import LLMWebEnricher


def build_default_record_quality_validator(
    config: AppConfig,
) -> RecordQualityValidator | None:
    if not config.llm_record_validation_enabled:
        return None

    if config.ai_provider is AIProvider.OPENAI and config.openai_api_key:
        return OpenAIBibliographicValidator(
            api_key=config.openai_api_key,
            base_url=config.openai_api_base_url,
            model=config.openai_model,
            timeout_seconds=config.request_timeout_seconds,
            min_confidence=config.llm_record_validation_min_confidence,
        )

    return None


def build_default_llm_enricher(config: AppConfig) -> LLMWebEnricher | None:
    if not config.llm_enrichment_enabled:
        return None

    if config.ai_provider is AIProvider.OPENAI and config.openai_api_key:
        return LLMWebEnricher(
            api_key=config.openai_api_key,
            base_url=config.openai_api_base_url,
            model=config.openai_model,
            timeout_seconds=config.llm_enrichment_timeout_seconds,
        )

    return None
