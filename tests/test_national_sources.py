from unittest.mock import Mock, patch

import httpx

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.national.base import StubNationalSource
from book_store_assistant.sources.national.colombia import ColombiaISBNSource


def _make_config(**overrides) -> AppConfig:
    defaults = dict(source_request_pause_seconds=0.0)
    defaults.update(overrides)
    return AppConfig(**defaults)


# ---- StubNationalSource tests ----


def test_stub_source_returns_not_implemented_issue_code() -> None:
    source = StubNationalSource("MX")
    result = source.fetch("9786071600011")

    assert result.record is None
    assert result.errors == []
    assert "NATIONAL_MX_NOT_IMPLEMENTED" in result.issue_codes


def test_stub_source_name_uses_lowercase_country() -> None:
    source = StubNationalSource("AR")

    assert source.source_name == "national_ar"
    assert source.country_code == "AR"


def test_stub_source_preserves_isbn_in_result() -> None:
    source = StubNationalSource("CL")
    result = source.fetch("9789561234567")

    assert result.isbn == "9789561234567"


def test_stub_source_different_countries_different_issue_codes() -> None:
    for country in ("BR", "PE", "VE", "UY", "EC", "BO", "GT", "CR", "PA"):
        source = StubNationalSource(country)
        result = source.fetch("9780000000000")

        expected_code = f"NATIONAL_{country}_NOT_IMPLEMENTED"
        assert expected_code in result.issue_codes, (
            f"Expected {expected_code} for country {country}"
        )


# ---- ColombiaISBNSource tests ----


_SAMPLE_HTML = """
<html>
<body>
<table>
<tr><td><b>Titulo:</b>&nbsp;La voragine<br></td></tr>
<tr><td><b>Autor:</b>&nbsp;Jose Eustasio Rivera<br></td></tr>
<tr><td><b>Editorial:</b>&nbsp;Editorial Colombia<br></td></tr>
</table>
</body>
</html>
"""

_SAMPLE_HTML_WITH_SELLO = """
<html>
<body>
<table>
<tr><td><b>Titulo:</b>&nbsp;Cien anos de soledad<br></td></tr>
<tr><td><b>Autor:</b>&nbsp;Gabriel Garcia Marquez<br></td></tr>
<tr><td><b>Sello:</b>&nbsp;Random House<br></td></tr>
</table>
</body>
</html>
"""

_EMPTY_HTML = """
<html>
<body>
<p>No results found.</p>
</body>
</html>
"""


@patch("book_store_assistant.sources.national.colombia.httpx.get")
def test_colombia_parses_html_fields(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = _SAMPLE_HTML
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = ColombiaISBNSource(_make_config())
    result = source.fetch("9789581234567")

    assert result.record is not None
    assert result.record.title == "La voragine"
    assert result.record.author == "Jose Eustasio Rivera"
    assert result.record.editorial == "Editorial Colombia"
    assert result.record.isbn == "9789581234567"
    assert result.record.source_name == "colombia_isbn"
    assert result.record.source_url is not None
    assert "9789581234567" in str(result.record.source_url)
    assert result.errors == []
    assert result.issue_codes == []


@patch("book_store_assistant.sources.national.colombia.httpx.get")
def test_colombia_parses_sello_as_editorial(mock_get: Mock) -> None:
    """The Colombia source falls back to Sello when Editorial is absent."""
    mock_response = Mock()
    mock_response.text = _SAMPLE_HTML_WITH_SELLO
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = ColombiaISBNSource(_make_config())
    result = source.fetch("9789581234567")

    assert result.record is not None
    assert result.record.title == "Cien anos de soledad"
    assert result.record.author == "Gabriel Garcia Marquez"
    assert result.record.editorial == "Random House"


@patch("book_store_assistant.sources.national.colombia.httpx.get")
def test_colombia_no_match_returns_no_record(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = _EMPTY_HTML
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = ColombiaISBNSource(_make_config())
    result = source.fetch("9789581234567")

    assert result.record is None
    assert "COLOMBIA_ISBN_NO_MATCH" in result.issue_codes
    assert result.raw_payload == _EMPTY_HTML


@patch("book_store_assistant.sources.national.colombia.httpx.get")
def test_colombia_404_returns_error(mock_get: Mock) -> None:
    request = httpx.Request(
        "GET", "https://isbn.camlibro.com.co/catalogo.php?mode=detalle&isbn=9789581234567"
    )
    response = httpx.Response(404, request=request, text="Not Found")
    mock_get.side_effect = httpx.HTTPStatusError(
        "not found", request=request, response=response
    )

    source = ColombiaISBNSource(_make_config())
    result = source.fetch("9789581234567")

    assert result.record is None
    assert "COLOMBIA_ISBN_HTTP_404" in result.issue_codes
    assert len(result.errors) > 0


@patch("book_store_assistant.sources.national.colombia.httpx.get")
def test_colombia_network_error_returns_graceful_failure(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.ConnectError("connection refused")

    source = ColombiaISBNSource(_make_config())
    result = source.fetch("9789581234567")

    assert result.record is None
    assert len(result.errors) > 0
    assert "COLOMBIA_ISBN_REQUEST_ERROR" in result.issue_codes


@patch("book_store_assistant.sources.national.colombia.httpx.get")
def test_colombia_timeout_returns_graceful_failure(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.ReadTimeout("read timeout")

    source = ColombiaISBNSource(_make_config())
    result = source.fetch("9789581234567")

    assert result.record is None
    assert len(result.errors) > 0
    assert "COLOMBIA_ISBN_TIMEOUT" in result.issue_codes


def test_colombia_source_name() -> None:
    source = ColombiaISBNSource(_make_config())

    assert source.source_name == "colombia_isbn"


def test_colombia_uses_default_config_when_none() -> None:
    source = ColombiaISBNSource()

    assert isinstance(source.config, AppConfig)


@patch("book_store_assistant.sources.national.colombia.httpx.get")
def test_colombia_raw_payload_stored_in_result(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = _SAMPLE_HTML
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = ColombiaISBNSource(_make_config())
    result = source.fetch("9789581234567")

    assert result.raw_payload == _SAMPLE_HTML


@patch("book_store_assistant.sources.national.colombia.httpx.get")
def test_colombia_raw_payload_stored_in_record(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = _SAMPLE_HTML
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = ColombiaISBNSource(_make_config())
    result = source.fetch("9789581234567")

    assert result.record is not None
    assert result.record.raw_source_payload == _SAMPLE_HTML
