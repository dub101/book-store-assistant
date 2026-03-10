from book_store_assistant.config import AIProvider, AppConfig
from book_store_assistant.enrichment.base import SynopsisGenerator
from book_store_assistant.enrichment.openai_generator import OpenAISynopsisGenerator


def build_default_synopsis_generator(config: AppConfig) -> SynopsisGenerator | None:
    if config.ai_provider is AIProvider.OPENAI and config.openai_api_key:
        return OpenAISynopsisGenerator(
            api_key=config.openai_api_key,
            base_url=config.openai_api_base_url,
            model=config.openai_model,
            timeout_seconds=config.request_timeout_seconds,
        )

    return None
