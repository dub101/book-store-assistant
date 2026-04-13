from unittest.mock import Mock, patch

import httpx

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.bne import BneSruSource


def test_bne_source_exposes_source_name() -> None:
    source = BneSruSource()

    assert source.source_name == "bne"


def test_bne_source_uses_default_config() -> None:
    source = BneSruSource()

    assert isinstance(source.config, AppConfig)


@patch("book_store_assistant.sources.bne.httpx.get")
def test_bne_source_fetches_and_parses_response(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = """\
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <records>
    <record>
      <recordData>
        <dc xmlns="http://purl.org/dc/elements/1.1/">
          <title>Example Title</title>
          <creator>Example Author</creator>
          <publisher>Example Editorial</publisher>
        </dc>
      </recordData>
    </record>
  </records>
</searchRetrieveResponse>
"""
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = BneSruSource()

    result = source.fetch("9780306406157")

    assert result.record is not None
    assert result.record.title == "Example Title"
    assert result.record.source_name == "bne"
    assert result.raw_payload is not None
    assert result.record.raw_source_payload == result.raw_payload
    assert result.errors == []
    assert result.issue_codes == []
    mock_get.assert_called_once()


@patch("book_store_assistant.sources.bne.httpx.get")
def test_bne_source_returns_no_match_when_record_is_missing(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = (
        '<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">'
        "<records />"
        "</searchRetrieveResponse>"
    )
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    source = BneSruSource()

    result = source.fetch("9780306406157")

    assert result.record is None
    assert result.errors == ["No BNE match found."]
    assert result.issue_codes == ["BNE_NO_MATCH"]


@patch("book_store_assistant.sources.bne.httpx.get")
def test_bne_source_returns_error_on_http_failure(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.HTTPError("boom")

    source = BneSruSource()

    result = source.fetch("9780306406157")

    assert result.record is None
    assert result.errors == ["boom"]
    assert result.issue_codes == ["BNE_FETCH_ERROR"]
