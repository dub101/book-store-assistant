from book_store_assistant.config import AIProvider, AppConfig
from book_store_assistant.enrichment.openai_generator import OpenAISynopsisGenerator
from book_store_assistant.enrichment.providers import build_default_synopsis_generator


def test_build_default_synopsis_generator_returns_none_without_api_key() -> None:
    config = AppConfig(openai_api_key=None)

    assert build_default_synopsis_generator(config) is None


def test_build_default_synopsis_generator_returns_openai_generator() -> None:
    config = AppConfig(
        ai_provider=AIProvider.OPENAI,
        openai_api_key="test-key",
        openai_model="gpt-4o-mini",
    )

    generator = build_default_synopsis_generator(config)

    assert isinstance(generator, OpenAISynopsisGenerator)
