from unittest.mock import Mock, patch

from book_store_assistant.resolution.openai_subject_mapper import OpenAISubjectMapper
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.subjects import SubjectEntry


@patch("book_store_assistant.resolution.openai_subject_mapper.httpx.post")
def test_openai_subject_mapper_returns_catalog_subject_on_high_confidence(mock_post: Mock) -> None:
    mock_response = Mock()
    mock_response.json.return_value = {
        "output_text": '{"subject":"FICCION","confidence":0.93}'
    }
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    mapper = OpenAISubjectMapper(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        timeout_seconds=10.0,
        min_confidence=0.85,
    )

    result = mapper.map_subject(
        SourceBookRecord(
            source_name="open_library",
            isbn="9780306406157",
            title="Example Title",
            categories=["Narrative fiction"],
        ),
        [SubjectEntry(subject="13", description="FICCION", subject_type="L0")],
    )

    assert result == "FICCION"


@patch("book_store_assistant.resolution.openai_subject_mapper.httpx.post")
def test_openai_subject_mapper_rejects_unknown_subject_or_low_confidence(mock_post: Mock) -> None:
    mock_response = Mock()
    mock_response.json.return_value = {
        "output_text": '{"subject":"UNKNOWN","confidence":0.99}'
    }
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    mapper = OpenAISubjectMapper(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        timeout_seconds=10.0,
        min_confidence=0.85,
    )

    result = mapper.map_subject(
        SourceBookRecord(
            source_name="open_library",
            isbn="9780306406157",
            title="Example Title",
            categories=["Narrative fiction"],
        ),
        [SubjectEntry(subject="13", description="FICCION", subject_type="L0")],
    )

    assert result is None
