from unittest.mock import Mock, patch

from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.publisher_identity.models import PublisherIdentityResult
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


@patch("book_store_assistant.resolution.openai_bibliographic_validator.httpx.post")
def test_bibliographic_validator_sends_publisher_identity_context(
    mock_post: Mock,
) -> None:
    mock_response = Mock()
    mock_response.json.return_value = {
        "output_text": '{"accepted":true,"confidence":0.98,"issues":[],"explanation":"ok"}'
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

    validator.validate(
        SourceBookRecord(
            source_name="bne",
            isbn="9788467026283",
            title="Educacion para la ciudadania y derechos humanos",
            author="Gregorio Peces-Barba Martinez",
            editorial="Espasa",
        ),
        BibliographicRecord(
            isbn="9788467026283",
            title="Educacion para la ciudadania y derechos humanos",
            author="Gregorio Peces-Barba Martinez",
            editorial="Espasa",
            publisher="Planeta",
        ),
        publisher_identity=PublisherIdentityResult(
            isbn="9788467026283",
            publisher_name="Planeta",
            imprint_name="Espasa",
            confidence=0.95,
            resolution_method="editorial_field",
            evidence=["editorial:Espasa"],
        ),
    )

    input_payload = mock_post.call_args.kwargs["json"]["input"]
    user_message = input_payload[1]["content"]
    assert "Resolved imprint/editorial: Espasa" in user_message
    assert "Resolved publisher/group: Planeta" in user_message
