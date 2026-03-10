from unittest.mock import Mock, patch

import httpx

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.open_library import OpenLibrarySource


def test_open_library_source_exposes_source_name() -> None:
    source = OpenLibrarySource()

    assert source.source_name == "open_library"


def test_open_library_source_uses_default_config() -> None:
    source = OpenLibrarySource()

    assert isinstance(source.config, AppConfig)


@patch("book_store_assistant.sources.open_library.httpx.get")
def test_open_library_source_fetches_and_parses_response(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.json.return_value = {
        "ISBN:9780306406157": {
            "title": "Example Title",
            "authors": [{"name": "Example Author"}],
            "publishers": [{"name": "Example Editorial"}],
        }
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = OpenLibrarySource()

    result = source.fetch("9780306406157")

    assert result.record is not None
    assert result.record.title == "Example Title"
    assert result.record.source_name == "open_library"
    assert result.errors == []
    assert result.issue_codes == []
    mock_get.assert_called_once()


@patch("book_store_assistant.sources.open_library.httpx.get")
def test_open_library_source_returns_error_on_http_failure(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.HTTPError("boom")

    source = OpenLibrarySource()

    result = source.fetch("9780306406157")

    assert result.record is None
    assert result.errors == ["boom"]
    assert result.issue_codes == ["OPEN_LIBRARY_FETCH_ERROR"]
