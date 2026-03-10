from unittest.mock import patch

import httpx

from book_store_assistant.enrichment.models import DescriptiveEvidence, GeneratedSynopsis
from book_store_assistant.enrichment.openai_generator import (
    OpenAISynopsisGenerator,
    _extract_output_text,
    _parse_generated_synopsis,
)


def test_extract_output_text_reads_top_level_output_text() -> None:
    payload = {"output_text": '{"text":"Resumen","language":"es","evidence_indexes":[0]}'}

    assert _extract_output_text(payload) == payload["output_text"]


def test_extract_output_text_reads_nested_output_content() -> None:
    payload = {
        "output": [
            {
                "content": [
                    {"text": '{"text":"Resumen","language":"es","evidence_indexes":[0]}'}
                ]
            }
        ]
    }

    assert _extract_output_text(payload) == (
        '{"text":"Resumen","language":"es","evidence_indexes":[0]}'
    )


def test_parse_generated_synopsis_returns_model() -> None:
    result = _parse_generated_synopsis(
        '{"text":"Resumen","language":"es","evidence_indexes":[0]}'
    )

    assert result == GeneratedSynopsis(
        text="Resumen",
        language="es",
        evidence_indexes=[0],
        raw_output_text='{"text":"Resumen","language":"es","evidence_indexes":[0]}',
    )


def test_parse_generated_synopsis_returns_none_for_invalid_json() -> None:
    assert _parse_generated_synopsis("not-json") is None


def test_parse_generated_synopsis_extracts_json_object_from_wrapped_text() -> None:
    result = _parse_generated_synopsis(
        '```json\n{"text":"Resumen","language":"es","evidence_indexes":[0]}\n```'
    )

    assert result == GeneratedSynopsis(
        text="Resumen",
        language="es",
        evidence_indexes=[0],
        raw_output_text='```json\n{"text":"Resumen","language":"es","evidence_indexes":[0]}\n```',
    )


@patch("book_store_assistant.enrichment.openai_generator.httpx.post")
def test_openai_generator_calls_responses_api(mock_post) -> None:
    mock_response = httpx.Response(
        200,
        request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        json={"output_text": '{"text":"Resumen","language":"es","evidence_indexes":[0]}'},
    )
    mock_post.return_value = mock_response

    generator = OpenAISynopsisGenerator(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        timeout_seconds=10.0,
    )

    result = generator.generate(
        "9780306406157",
        [
            DescriptiveEvidence(
                source_name="google_books",
                evidence_type="source_synopsis",
                evidence_origin="direct_source_record",
                text="This is enough grounded evidence to generate a Spanish synopsis safely.",
                language="en",
                extraction_method="source_synopsis_field",
            )
        ],
    )

    assert result == GeneratedSynopsis(
        text="Resumen",
        language="es",
        evidence_indexes=[0],
        raw_output_text='{"text":"Resumen","language":"es","evidence_indexes":[0]}',
    )
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert mock_post.call_args.kwargs["json"]["model"] == "gpt-4o-mini"
    assert mock_post.call_args.kwargs["json"]["text"]["format"]["type"] == "json_schema"
