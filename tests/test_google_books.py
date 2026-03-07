from book_store_assistant.config import AppConfig
from book_store_assistant.sources.google_books import GoogleBooksSource


def test_google_books_source_exposes_source_name() -> None:
    source = GoogleBooksSource()

    assert source.source_name == "google_books"


def test_google_books_source_uses_default_config() -> None:
    source = GoogleBooksSource()

    assert isinstance(source.config, AppConfig)
