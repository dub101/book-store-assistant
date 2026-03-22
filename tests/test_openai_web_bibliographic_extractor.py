from unittest.mock import Mock, patch

import httpx

from book_store_assistant.bibliographic.evidence import (
    WebSearchBibliographicExtraction,
    WebSearchEvidenceDocument,
)
from book_store_assistant.bibliographic.openai_extractor import (
    OpenAIWebBibliographicExtractor,
)
from book_store_assistant.sources.models import SourceBookRecord


def _evidence_documents() -> list[WebSearchEvidenceDocument]:
    return [
        WebSearchEvidenceDocument(
            index=0,
            url="https://www.planetadelibros.com/libro/ejemplo/123",
            domain="www.planetadelibros.com",
            page_title="Example Title",
            excerpt=(
                "ISBN 9780306406157 Title Example Title "
                "Author Example Author Editorial Planeta."
            ),
        )
    ]


@patch("book_store_assistant.bibliographic.openai_extractor.httpx.post")
def test_openai_web_bibliographic_extractor_returns_grounded_extraction(mock_post: Mock) -> None:
    mock_response = Mock()
    mock_response.json.return_value = {
        "output_text": (
            '{"confidence":0.94,"title":"Example Title","subtitle":null,'
            '"author":"Example Author","editorial":"Planeta","publisher":"Planeta",'
            '"support":{"title":[0],"subtitle":[],"author":[0],"editorial":[0],"publisher":[0]},'
            '"issues":[],"explanation":"Grounded in the supplied page."}'
        )
    }
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    extractor = OpenAIWebBibliographicExtractor(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        timeout_seconds=10.0,
        min_confidence=0.75,
    )

    result = extractor.extract(
        SourceBookRecord(source_name="bne", isbn="9780306406157"),
        _evidence_documents(),
    )

    assert result == WebSearchBibliographicExtraction(
        confidence=0.94,
        title="Example Title",
        subtitle=None,
        author="Example Author",
        editorial="Planeta",
        publisher="Planeta",
        support={
            "title": [0],
            "subtitle": [],
            "author": [0],
            "editorial": [0],
            "publisher": [0],
        },
        issues=[],
        explanation="Grounded in the supplied page.",
        raw_output_text=mock_response.json.return_value["output_text"],
    )


@patch("book_store_assistant.bibliographic.openai_extractor.httpx.post")
def test_openai_web_bibliographic_extractor_marks_low_confidence_outputs(mock_post: Mock) -> None:
    mock_response = Mock()
    mock_response.json.return_value = {
        "output_text": (
            '{"confidence":0.61,"title":"Example Title","subtitle":null,'
            '"author":"Example Author","editorial":"Planeta","publisher":"Planeta",'
            '"support":{"title":[0],"subtitle":[],"author":[0],"editorial":[0],"publisher":[0]},'
            '"issues":[],"explanation":"Possibly grounded but low confidence."}'
        )
    }
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    extractor = OpenAIWebBibliographicExtractor(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        timeout_seconds=10.0,
        min_confidence=0.75,
    )

    result = extractor.extract(
        SourceBookRecord(source_name="bne", isbn="9780306406157"),
        _evidence_documents(),
    )

    assert result is not None
    assert "extractor_low_confidence" in result.issues


@patch("book_store_assistant.bibliographic.openai_extractor.httpx.post")
def test_openai_web_bibliographic_extractor_returns_none_on_http_error(mock_post: Mock) -> None:
    mock_post.side_effect = httpx.ReadTimeout("timed out")

    extractor = OpenAIWebBibliographicExtractor(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        timeout_seconds=10.0,
        min_confidence=0.75,
    )

    result = extractor.extract(
        SourceBookRecord(source_name="bne", isbn="9780306406157"),
        _evidence_documents(),
    )

    assert result is None
