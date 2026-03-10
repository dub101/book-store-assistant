from unittest.mock import Mock, call, patch

import httpx

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

    result = source.fetch("9780306406157")

    assert result.record is not None
    assert result.record.title == "Example Title"
    assert result.errors == []
    assert result.issue_codes == []
    mock_get.assert_called_once()


@patch("book_store_assistant.sources.google_books.time.sleep")
@patch("book_store_assistant.sources.google_books.httpx.get")
def test_google_books_source_retries_rate_limits_and_preserves_issue_codes(
    mock_get: Mock,
    mock_sleep: Mock,
) -> None:
    request = httpx.Request("GET", "https://example.com")
    rate_limited_response = httpx.Response(
        429,
        headers={"Retry-After": "0"},
        request=request,
    )
    success_response = Mock()
    success_response.json.return_value = {
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
    success_response.raise_for_status.return_value = None
    mock_get.side_effect = [
        httpx.HTTPStatusError(
            "rate limited",
            request=request,
            response=rate_limited_response,
        ),
        success_response,
    ]

    source = GoogleBooksSource()

    result = source.fetch("9780306406157")

    assert result.record is not None
    assert result.record.title == "Example Title"
    assert result.errors == []
    assert result.issue_codes == ["GOOGLE_BOOKS_HTTP_429", "GOOGLE_BOOKS_RATE_LIMITED"]
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(0.0)


@patch("book_store_assistant.sources.google_books.httpx.get")
def test_google_books_source_returns_error_on_http_failure(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.HTTPError("boom")

    source = GoogleBooksSource()

    result = source.fetch("9780306406157")

    assert result.record is None
    assert result.errors == ["boom"]
    assert result.issue_codes == ["GOOGLE_BOOKS_FETCH_ERROR"]


@patch("book_store_assistant.sources.google_books.httpx.get")
def test_google_books_source_classifies_rate_limit_errors(mock_get: Mock) -> None:
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(429, request=request)
    mock_get.side_effect = httpx.HTTPStatusError("rate limited", request=request, response=response)

    source = GoogleBooksSource()

    result = source.fetch("9780306406157")

    assert result.issue_codes == ["GOOGLE_BOOKS_HTTP_429", "GOOGLE_BOOKS_RATE_LIMITED"]


@patch("book_store_assistant.sources.google_books.time.sleep")
@patch("book_store_assistant.sources.google_books.httpx.get")
def test_google_books_source_stops_retrying_after_configured_attempts(
    mock_get: Mock,
    mock_sleep: Mock,
) -> None:
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(429, request=request)
    mock_get.side_effect = [
        httpx.HTTPStatusError("rate limited", request=request, response=response),
        httpx.HTTPStatusError("rate limited", request=request, response=response),
        httpx.HTTPStatusError("rate limited", request=request, response=response),
    ]

    source = GoogleBooksSource(
        AppConfig(
            google_books_max_retries=2,
            google_books_backoff_seconds=0.5,
        )
    )

    result = source.fetch("9780306406157")

    assert result.record is None
    assert result.errors == ["rate limited"]
    assert result.issue_codes == ["GOOGLE_BOOKS_HTTP_429", "GOOGLE_BOOKS_RATE_LIMITED"]
    assert mock_get.call_count == 3
    assert mock_sleep.call_args_list == [call(0.5), call(1.0)]
