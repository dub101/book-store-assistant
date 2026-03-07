from unittest.mock import Mock, patch

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.google_books import GoogleBooksSource


def test_google_books_source_exposes_source_name() -> None:
    source = GoogleBooksSource()

    assert source.source_name == "google_books"


def test_google_books_source_uses_default_config() -> None:
    source = GoogleBooksSource()

    assert isinstance(source.config, AppConfig)


@patch("book_store_assistant.sources.google_books.httpx.get")
def test_google_books_source_fetches_and_parses_response(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.json.return_value = {
        "items": [
            {
                "volumeInfo": {
                    "title": "Example Title",
                    "authors": ["Example Author"],
                    "publisher": "Example Editorial",
                }
            }
        ]
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = GoogleBooksSource()

    record = source.fetch("9780306406157")

    assert record is not None
    assert record.title == "Example Title"
    mock_get.assert_called_once()
