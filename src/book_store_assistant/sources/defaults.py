from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.google_books import GoogleBooksSource
from book_store_assistant.sources.open_library import OpenLibrarySource


def build_default_sources() -> list[MetadataSource]:
    """Return sources in precedence order for multi-source merging."""
    return [
        GoogleBooksSource(),
        OpenLibrarySource(),
    ]
