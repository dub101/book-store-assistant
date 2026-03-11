from book_store_assistant.config import AppConfig
from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.cache import CachedMetadataSource
from book_store_assistant.sources.google_books import GoogleBooksSource
from book_store_assistant.sources.open_library import OpenLibrarySource

DEFAULT_SOURCE_CACHE_KEY = "default_metadata_sources_v1"


def build_default_sources(config: AppConfig | None = None) -> list[MetadataSource]:
    """Return sources in precedence order for multi-source merging."""
    active_config = config or AppConfig()
    return [
        GoogleBooksSource(active_config),
        OpenLibrarySource(active_config),
    ]


def wrap_with_default_cache(
    source: MetadataSource,
    config: AppConfig | None = None,
) -> MetadataSource:
    active_config = config or AppConfig()
    if not active_config.source_cache_enabled:
        return source

    return CachedMetadataSource(
        source=source,
        cache_dir=active_config.source_cache_dir,
        source_key=DEFAULT_SOURCE_CACHE_KEY,
    )
