from unittest.mock import Mock, patch

import httpx

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.isbndb import ISBNdbSource


def _make_config(**overrides) -> AppConfig:
    defaults = dict(
        source_request_pause_seconds=0.0,
        isbndb_api_key="test-api-key",
    )
    defaults.update(overrides)
    return AppConfig(**defaults)


@patch("book_store_assistant.sources.isbndb.httpx.get")
def test_successful_fetch_returns_record(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.json.return_value = {
        "book": {
            "title": "Example Title",
            "authors": ["Author One"],
            "publisher": "Publisher",
        }
    }
    mock_response.raise_for_status.return_value = None
    mock_response.text = '{"book": {}}'
    mock_get.return_value = mock_response

    source = ISBNdbSource(_make_config())
    result = source.fetch("9780306406157")

    assert result.record is not None
    assert result.record.title == "Example Title"
    assert result.record.author == "Author One"
    assert result.record.editorial == "Publisher"
    assert result.record.source_name == "isbndb"
    assert result.raw_payload is not None
    assert result.record.raw_source_payload == result.raw_payload
    assert result.errors == []
    assert result.issue_codes == []
    mock_get.assert_called_once()


@patch("book_store_assistant.sources.isbndb.httpx.get")
def test_404_returns_no_record_with_issue_code(mock_get: Mock) -> None:
    request = httpx.Request("GET", "https://api2.isbndb.com/book/9780306406157")
    response = httpx.Response(404, request=request)
    mock_get.side_effect = httpx.HTTPStatusError(
        "not found", request=request, response=response
    )

    source = ISBNdbSource(_make_config())
    result = source.fetch("9780306406157")

    assert result.record is None
    assert "ISBNDB_HTTP_404" in result.issue_codes
    assert len(result.errors) > 0


@patch("book_store_assistant.sources.isbndb.time.sleep")
@patch("book_store_assistant.sources.isbndb.httpx.get")
def test_429_retries_with_backoff_and_adaptive_pause_increases(
    mock_get: Mock,
    mock_sleep: Mock,
) -> None:
    request = httpx.Request("GET", "https://api2.isbndb.com/book/9780306406157")
    rate_limited_response = httpx.Response(
        429, headers={"Retry-After": "0"}, request=request
    )
    success_response = Mock()
    success_response.json.return_value = {
        "book": {
            "title": "Retried Book",
            "authors": ["Author"],
        }
    }
    success_response.raise_for_status.return_value = None
    mock_get.side_effect = [
        httpx.HTTPStatusError(
            "rate limited", request=request, response=rate_limited_response
        ),
        success_response,
    ]

    source = ISBNdbSource(_make_config())
    assert source.adaptive_pause == 0.0

    result = source.fetch("9780306406157")

    assert result.record is not None
    assert result.record.title == "Retried Book"
    assert source.adaptive_pause >= 0.5
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()
    assert "ISBNDB_HTTP_429" in result.issue_codes
    assert "ISBNDB_RATE_LIMITED" in result.issue_codes


@patch("book_store_assistant.sources.isbndb.time.sleep")
@patch("book_store_assistant.sources.isbndb.httpx.get")
def test_429_exhausts_retries(mock_get: Mock, mock_sleep: Mock) -> None:
    request = httpx.Request("GET", "https://api2.isbndb.com/book/9780306406157")
    response = httpx.Response(429, request=request)
    mock_get.side_effect = [
        httpx.HTTPStatusError("rate limited", request=request, response=response)
        for _ in range(4)
    ]

    source = ISBNdbSource(_make_config())
    result = source.fetch("9780306406157")

    assert result.record is None
    assert "ISBNDB_HTTP_429" in result.issue_codes
    assert "ISBNDB_RATE_LIMITED" in result.issue_codes
    assert mock_get.call_count == 4  # initial + 3 retries
    assert mock_sleep.call_count == 3


def test_no_api_key_returns_isbndb_no_api_key() -> None:
    config = _make_config(isbndb_api_key=None)
    source = ISBNdbSource(config)

    result = source.fetch("9780306406157")

    assert result.record is None
    assert "ISBNDB_NO_API_KEY" in result.issue_codes
    assert len(result.errors) > 0


@patch("book_store_assistant.sources.isbndb.httpx.get")
def test_network_error_returns_error(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.ConnectError("connection refused")

    source = ISBNdbSource(_make_config())
    result = source.fetch("9780306406157")

    assert result.record is None
    assert len(result.errors) > 0
    assert "ISBNDB_REQUEST_ERROR" in result.issue_codes


@patch("book_store_assistant.sources.isbndb.httpx.get")
def test_timeout_error_returns_error(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.ReadTimeout("read timeout")

    source = ISBNdbSource(_make_config())
    result = source.fetch("9780306406157")

    assert result.record is None
    assert len(result.errors) > 0
    assert "ISBNDB_TIMEOUT" in result.issue_codes


@patch("book_store_assistant.sources.isbndb.httpx.get")
def test_successful_response_with_no_book_returns_no_match(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.json.return_value = {"error": "not found"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = ISBNdbSource(_make_config())
    result = source.fetch("9780306406157")

    assert result.record is None
    assert "ISBNDB_NO_MATCH" in result.issue_codes


def test_source_name() -> None:
    source = ISBNdbSource(_make_config())

    assert source.source_name == "isbndb"


def test_uses_default_config_when_none() -> None:
    source = ISBNdbSource()

    assert isinstance(source.config, AppConfig)


@patch("book_store_assistant.sources.isbndb.httpx.get")
def test_fetch_passes_authorization_header(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.json.return_value = {
        "book": {"title": "Test"}
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    config = _make_config(isbndb_api_key="my-secret-key")
    source = ISBNdbSource(config)
    source.fetch("9780306406157")

    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args
    assert call_kwargs.kwargs["headers"]["Authorization"] == "my-secret-key"


@patch("book_store_assistant.sources.isbndb.time.sleep")
@patch("book_store_assistant.sources.isbndb.httpx.get")
def test_retry_delay_uses_retry_after_header(
    mock_get: Mock,
    mock_sleep: Mock,
) -> None:
    request = httpx.Request("GET", "https://api2.isbndb.com/book/9780306406157")
    rate_limited_response = httpx.Response(
        429, headers={"Retry-After": "5"}, request=request
    )
    success_response = Mock()
    success_response.json.return_value = {
        "book": {"title": "Retried"}
    }
    success_response.raise_for_status.return_value = None
    mock_get.side_effect = [
        httpx.HTTPStatusError(
            "rate limited", request=request, response=rate_limited_response
        ),
        success_response,
    ]

    source = ISBNdbSource(_make_config())
    source.fetch("9780306406157")

    mock_sleep.assert_called_once_with(5.0)
