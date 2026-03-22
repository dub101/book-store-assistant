from unittest.mock import Mock, patch

from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.resolution.openai_bibliographic_validator import (
    OpenAIBibliographicValidator,
)
from book_store_assistant.sources.models import SourceBookRecord


@patch("book_store_assistant.resolution.openai_bibliographic_validator.httpx.post")
def test_bibliographic_validator_keeps_accepted_rows_even_with_low_confidence(
    mock_post: Mock,
) -> None:
    mock_response = Mock()
    mock_response.json.return_value = {
        "output_text": (
            '{"accepted":true,"confidence":0.0,"issues":[],'
            '"explanation":"The row matches the evidence."}'
        )
    }
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    validator = OpenAIBibliographicValidator(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        timeout_seconds=10.0,
        min_confidence=0.8,
    )

    result = validator.validate(
        SourceBookRecord(
            source_name="bne + web_search",
            isbn="9780306406157",
            title="Example Title",
            author="Example Author",
            editorial="Planeta",
        ),
        BibliographicRecord(
            isbn="9780306406157",
            title="Example Title",
            author="Example Author",
            editorial="Planeta",
            publisher="Planeta",
        ),
    )

    assert result is not None
    assert result.accepted is True
    assert "validator_low_confidence" in result.issues
