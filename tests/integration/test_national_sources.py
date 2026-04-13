import json
from unittest.mock import Mock, patch

import httpx

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.national.argentina import ArgentinaISBNSource
from book_store_assistant.sources.national.base import StubNationalSource
from book_store_assistant.sources.national.brazil import BrazilISBNSource
from book_store_assistant.sources.national.chile import ChileISBNSource
from book_store_assistant.sources.national.colombia import ColombiaISBNSource
from book_store_assistant.sources.national.ecuador import EcuadorISBNSource
from book_store_assistant.sources.national.mexico import MexicoISBNSource
from book_store_assistant.sources.national.peru import PeruISBNSource
from book_store_assistant.sources.national.uruguay import UruguayISBNSource
from book_store_assistant.sources.national.venezuela import VenezuelaISBNSource


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


# ---- Helper HTML for HTML-based national sources ----


def _html_page(title: str, author: str, editorial: str) -> str:
    return f"""
<html>
<body>
<table>
<tr><td><b>Titulo:</b>&nbsp;{title}<br></td></tr>
<tr><td><b>Autor:</b>&nbsp;{author}<br></td></tr>
<tr><td><b>Editorial:</b>&nbsp;{editorial}<br></td></tr>
</table>
</body>
</html>
"""


_NO_MATCH_HTML = """
<html>
<body>
<p>No results found.</p>
</body>
</html>
"""


# ---- MexicoISBNSource tests ----


_MEXICO_HTML = _html_page(
    "Pedro Paramo", "Juan Rulfo", "Fondo de Cultura Economica"
)


@patch("book_store_assistant.sources.national.mexico.httpx.get")
def test_mexico_parses_html_fields(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = _MEXICO_HTML
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = MexicoISBNSource(_make_config())
    result = source.fetch("9786071600011")

    assert result.record is not None
    assert result.record.title == "Pedro Paramo"
    assert result.record.author == "Juan Rulfo"
    assert result.record.editorial == "Fondo de Cultura Economica"
    assert result.record.isbn == "9786071600011"
    assert result.record.source_name == "mexico_isbn"
    assert result.errors == []
    assert result.issue_codes == []


@patch("book_store_assistant.sources.national.mexico.httpx.get")
def test_mexico_404_returns_no_record(mock_get: Mock) -> None:
    request = httpx.Request(
        "GET",
        "https://isbnmexico.indautor.cerlalc.org/catalogo.php?mode=detalle&isbn=9786071600011",
    )
    response = httpx.Response(404, request=request, text="Not Found")
    mock_get.side_effect = httpx.HTTPStatusError(
        "not found", request=request, response=response
    )

    source = MexicoISBNSource(_make_config())
    result = source.fetch("9786071600011")

    assert result.record is None
    assert "MEXICO_ISBN_HTTP_404" in result.issue_codes
    assert len(result.errors) > 0


@patch("book_store_assistant.sources.national.mexico.httpx.get")
def test_mexico_network_error_returns_graceful_failure(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.ConnectError("connection refused")

    source = MexicoISBNSource(_make_config())
    result = source.fetch("9786071600011")

    assert result.record is None
    assert len(result.errors) > 0
    assert "MEXICO_ISBN_REQUEST_ERROR" in result.issue_codes


# ---- ArgentinaISBNSource tests ----


_ARGENTINA_HTML = _html_page(
    "El tunel", "Ernesto Sabato", "Editorial Sudamericana"
)


@patch("book_store_assistant.sources.national.argentina.httpx.get")
def test_argentina_parses_html_fields(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = _ARGENTINA_HTML
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = ArgentinaISBNSource(_make_config())
    result = source.fetch("9789500000000")

    assert result.record is not None
    assert result.record.title == "El tunel"
    assert result.record.author == "Ernesto Sabato"
    assert result.record.editorial == "Editorial Sudamericana"
    assert result.record.isbn == "9789500000000"
    assert result.record.source_name == "argentina_isbn"
    assert result.errors == []
    assert result.issue_codes == []


@patch("book_store_assistant.sources.national.argentina.httpx.get")
def test_argentina_404_returns_no_record(mock_get: Mock) -> None:
    request = httpx.Request(
        "GET", "https://www.isbn.org.ar/web/buscar-detalle.php?isbn=9789500000000"
    )
    response = httpx.Response(404, request=request, text="Not Found")
    mock_get.side_effect = httpx.HTTPStatusError(
        "not found", request=request, response=response
    )

    source = ArgentinaISBNSource(_make_config())
    result = source.fetch("9789500000000")

    assert result.record is None
    assert "ARGENTINA_ISBN_HTTP_404" in result.issue_codes
    assert len(result.errors) > 0


@patch("book_store_assistant.sources.national.argentina.httpx.get")
def test_argentina_network_error_returns_graceful_failure(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.ConnectError("connection refused")

    source = ArgentinaISBNSource(_make_config())
    result = source.fetch("9789500000000")

    assert result.record is None
    assert len(result.errors) > 0
    assert "ARGENTINA_ISBN_REQUEST_ERROR" in result.issue_codes


# ---- ChileISBNSource tests ----


_CHILE_HTML = _html_page(
    "La casa de los espiritus", "Isabel Allende", "Editorial Planeta Chile"
)


@patch("book_store_assistant.sources.national.chile.httpx.get")
def test_chile_parses_html_fields(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = _CHILE_HTML
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = ChileISBNSource(_make_config())
    result = source.fetch("9789561234567")

    assert result.record is not None
    assert result.record.title == "La casa de los espiritus"
    assert result.record.author == "Isabel Allende"
    assert result.record.editorial == "Editorial Planeta Chile"
    assert result.record.isbn == "9789561234567"
    assert result.record.source_name == "chile_isbn"
    assert result.errors == []
    assert result.issue_codes == []


@patch("book_store_assistant.sources.national.chile.httpx.get")
def test_chile_404_returns_no_record(mock_get: Mock) -> None:
    request = httpx.Request(
        "GET",
        "https://isbnchile.cl/catalogo.php?mode=detalle&isbn=9789561234567",
    )
    response = httpx.Response(404, request=request, text="Not Found")
    mock_get.side_effect = httpx.HTTPStatusError(
        "not found", request=request, response=response
    )

    source = ChileISBNSource(_make_config())
    result = source.fetch("9789561234567")

    assert result.record is None
    assert "CHILE_ISBN_HTTP_404" in result.issue_codes
    assert len(result.errors) > 0


@patch("book_store_assistant.sources.national.chile.httpx.get")
def test_chile_network_error_returns_graceful_failure(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.ConnectError("connection refused")

    source = ChileISBNSource(_make_config())
    result = source.fetch("9789561234567")

    assert result.record is None
    assert len(result.errors) > 0
    assert "CHILE_ISBN_REQUEST_ERROR" in result.issue_codes


# ---- PeruISBNSource tests ----


_PERU_HTML = _html_page(
    "La ciudad y los perros", "Mario Vargas Llosa", "Peisa"
)


@patch("book_store_assistant.sources.national.peru.httpx.get")
def test_peru_parses_html_fields(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = _PERU_HTML
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = PeruISBNSource(_make_config())
    result = source.fetch("9789972000000")

    assert result.record is not None
    assert result.record.title == "La ciudad y los perros"
    assert result.record.author == "Mario Vargas Llosa"
    assert result.record.editorial == "Peisa"
    assert result.record.isbn == "9789972000000"
    assert result.record.source_name == "peru_isbn"
    assert result.errors == []
    assert result.issue_codes == []


@patch("book_store_assistant.sources.national.peru.httpx.get")
def test_peru_404_returns_no_record(mock_get: Mock) -> None:
    request = httpx.Request(
        "GET",
        "https://isbn.bnp.gob.pe/catalogo.php?mode=detalle&isbn=9789972000000",
    )
    response = httpx.Response(404, request=request, text="Not Found")
    mock_get.side_effect = httpx.HTTPStatusError(
        "not found", request=request, response=response
    )

    source = PeruISBNSource(_make_config())
    result = source.fetch("9789972000000")

    assert result.record is None
    assert "PERU_ISBN_HTTP_404" in result.issue_codes
    assert len(result.errors) > 0


@patch("book_store_assistant.sources.national.peru.httpx.get")
def test_peru_network_error_returns_graceful_failure(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.ConnectError("connection refused")

    source = PeruISBNSource(_make_config())
    result = source.fetch("9789972000000")

    assert result.record is None
    assert len(result.errors) > 0
    assert "PERU_ISBN_REQUEST_ERROR" in result.issue_codes


# ---- VenezuelaISBNSource tests ----


_VENEZUELA_HTML = _html_page(
    "Dona Barbara", "Romulo Gallegos", "Monte Avila Editores"
)


@patch("book_store_assistant.sources.national.venezuela.httpx.get")
def test_venezuela_parses_html_fields(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = _VENEZUELA_HTML
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = VenezuelaISBNSource(_make_config())
    result = source.fetch("9789800000000")

    assert result.record is not None
    assert result.record.title == "Dona Barbara"
    assert result.record.author == "Romulo Gallegos"
    assert result.record.editorial == "Monte Avila Editores"
    assert result.record.isbn == "9789800000000"
    assert result.record.source_name == "venezuela_isbn"
    assert result.errors == []
    assert result.issue_codes == []


@patch("book_store_assistant.sources.national.venezuela.httpx.get")
def test_venezuela_404_returns_no_record(mock_get: Mock) -> None:
    request = httpx.Request(
        "GET",
        "http://isbn.cenal.gob.ve/catalogo.php?mode=detalle&isbn=9789800000000",
    )
    response = httpx.Response(404, request=request, text="Not Found")
    mock_get.side_effect = httpx.HTTPStatusError(
        "not found", request=request, response=response
    )

    source = VenezuelaISBNSource(_make_config())
    result = source.fetch("9789800000000")

    assert result.record is None
    assert "VENEZUELA_ISBN_HTTP_404" in result.issue_codes
    assert len(result.errors) > 0


@patch("book_store_assistant.sources.national.venezuela.httpx.get")
def test_venezuela_network_error_returns_graceful_failure(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.ConnectError("connection refused")

    source = VenezuelaISBNSource(_make_config())
    result = source.fetch("9789800000000")

    assert result.record is None
    assert len(result.errors) > 0
    assert "VENEZUELA_ISBN_REQUEST_ERROR" in result.issue_codes


# ---- EcuadorISBNSource tests ----


_ECUADOR_HTML = _html_page(
    "Huasipungo", "Jorge Icaza", "Editorial Losada"
)


@patch("book_store_assistant.sources.national.ecuador.httpx.get")
def test_ecuador_parses_html_fields(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = _ECUADOR_HTML
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = EcuadorISBNSource(_make_config())
    result = source.fetch("9789978000000")

    assert result.record is not None
    assert result.record.title == "Huasipungo"
    assert result.record.author == "Jorge Icaza"
    assert result.record.editorial == "Editorial Losada"
    assert result.record.isbn == "9789978000000"
    assert result.record.source_name == "ecuador_isbn"
    assert result.errors == []
    assert result.issue_codes == []


@patch("book_store_assistant.sources.national.ecuador.httpx.get")
def test_ecuador_404_returns_no_record(mock_get: Mock) -> None:
    request = httpx.Request(
        "GET",
        "https://isbnecuador.com/catalogo.php?mode=detalle&isbn=9789978000000",
    )
    response = httpx.Response(404, request=request, text="Not Found")
    mock_get.side_effect = httpx.HTTPStatusError(
        "not found", request=request, response=response
    )

    source = EcuadorISBNSource(_make_config())
    result = source.fetch("9789978000000")

    assert result.record is None
    assert "ECUADOR_ISBN_HTTP_404" in result.issue_codes
    assert len(result.errors) > 0


@patch("book_store_assistant.sources.national.ecuador.httpx.get")
def test_ecuador_network_error_returns_graceful_failure(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.ConnectError("connection refused")

    source = EcuadorISBNSource(_make_config())
    result = source.fetch("9789978000000")

    assert result.record is None
    assert len(result.errors) > 0
    assert "ECUADOR_ISBN_REQUEST_ERROR" in result.issue_codes


# ---- UruguayISBNSource tests ----


_URUGUAY_HTML = _html_page(
    "El pozo", "Juan Carlos Onetti", "Ediciones de la Banda Oriental"
)


@patch("book_store_assistant.sources.national.uruguay.httpx.get")
def test_uruguay_parses_html_fields(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = _URUGUAY_HTML
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = UruguayISBNSource(_make_config())
    result = source.fetch("9789974000000")

    assert result.record is not None
    assert result.record.title == "El pozo"
    assert result.record.author == "Juan Carlos Onetti"
    assert result.record.editorial == "Ediciones de la Banda Oriental"
    assert result.record.isbn == "9789974000000"
    assert result.record.source_name == "uruguay_isbn"
    assert result.errors == []
    assert result.issue_codes == []


@patch("book_store_assistant.sources.national.uruguay.httpx.get")
def test_uruguay_404_returns_no_record(mock_get: Mock) -> None:
    request = httpx.Request(
        "GET",
        "https://www.bibna.gub.uy/isbn/catalogo.php?mode=detalle&isbn=9789974000000",
    )
    response = httpx.Response(404, request=request, text="Not Found")
    mock_get.side_effect = httpx.HTTPStatusError(
        "not found", request=request, response=response
    )

    source = UruguayISBNSource(_make_config())
    result = source.fetch("9789974000000")

    assert result.record is None
    assert "URUGUAY_ISBN_HTTP_404" in result.issue_codes
    assert len(result.errors) > 0


@patch("book_store_assistant.sources.national.uruguay.httpx.get")
def test_uruguay_network_error_returns_graceful_failure(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.ConnectError("connection refused")

    source = UruguayISBNSource(_make_config())
    result = source.fetch("9789974000000")

    assert result.record is None
    assert len(result.errors) > 0
    assert "URUGUAY_ISBN_REQUEST_ERROR" in result.issue_codes


# ---- BrazilISBNSource tests (JSON-based) ----


_BRAZIL_JSON = json.dumps(
    {
        "isbn": "9788535902778",
        "titulo": "Grande Sertao: Veredas",
        "autores": ["Joao Guimaraes Rosa"],
        "editora": "Nova Fronteira",
    }
)

_BRAZIL_EMPTY_JSON = json.dumps({})


@patch("book_store_assistant.sources.national.brazil.httpx.get")
def test_brazil_parses_json_fields(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = _BRAZIL_JSON
    mock_response.json.return_value = json.loads(_BRAZIL_JSON)
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = BrazilISBNSource(_make_config())
    result = source.fetch("9788535902778")

    assert result.record is not None
    assert result.record.title == "Grande Sertao: Veredas"
    assert result.record.author == "Joao Guimaraes Rosa"
    assert result.record.editorial == "Nova Fronteira"
    assert result.record.isbn == "9788535902778"
    assert result.record.source_name == "brazil_isbn"
    assert result.errors == []
    assert result.issue_codes == []


@patch("book_store_assistant.sources.national.brazil.httpx.get")
def test_brazil_404_returns_no_record(mock_get: Mock) -> None:
    request = httpx.Request(
        "GET", "https://brasilapi.com.br/api/isbn/v1/9788535902778"
    )
    response = httpx.Response(404, request=request, text="Not Found")
    mock_get.side_effect = httpx.HTTPStatusError(
        "not found", request=request, response=response
    )

    source = BrazilISBNSource(_make_config())
    result = source.fetch("9788535902778")

    assert result.record is None
    assert "BRAZIL_ISBN_HTTP_404" in result.issue_codes
    assert len(result.errors) > 0


@patch("book_store_assistant.sources.national.brazil.httpx.get")
def test_brazil_network_error_returns_graceful_failure(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.ConnectError("connection refused")

    source = BrazilISBNSource(_make_config())
    result = source.fetch("9788535902778")

    assert result.record is None
    assert len(result.errors) > 0
    assert "BRAZIL_ISBN_REQUEST_ERROR" in result.issue_codes
