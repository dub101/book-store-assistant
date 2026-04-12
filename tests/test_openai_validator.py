"""Tests for the OpenAI bibliographic validator module."""

import json
from unittest.mock import MagicMock, patch

import httpx

from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.resolution.openai_bibliographic_validator import (
    OpenAIBibliographicValidator,
    _build_messages,
    _extract_output_text,
    _parse_validation_response,
)
from book_store_assistant.sources.models import SourceBookRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source_record(**overrides) -> SourceBookRecord:
    defaults = dict(
        source_name="google_books",
        isbn="9780306406157",
        title="Test Title",
        author="Test Author",
        editorial="Test Editorial",
        language="es",
        categories=["Fiction", "Drama"],
        field_sources={"title": "google_books", "author": "google_books"},
    )
    defaults.update(overrides)
    return SourceBookRecord(**defaults)


def _make_candidate_record(**overrides) -> BibliographicRecord:
    defaults = dict(
        isbn="9780306406157",
        title="Test Title",
        subtitle="A Subtitle",
        author="Test Author",
        editorial="Test Editorial",
        synopsis="A test synopsis.",
        subject="NOVELA",
        subject_code="2000",
    )
    defaults.update(overrides)
    return BibliographicRecord(**defaults)


def _make_validator(**overrides) -> OpenAIBibliographicValidator:
    defaults = dict(
        api_key="sk-test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        timeout_seconds=10.0,
        min_confidence=0.8,
    )
    defaults.update(overrides)
    return OpenAIBibliographicValidator(**defaults)


# ---------------------------------------------------------------------------
# _build_messages
# ---------------------------------------------------------------------------


class TestBuildMessages:
    def test_creates_system_and_user_messages(self) -> None:
        source = _make_source_record()
        candidate = _make_candidate_record()

        messages = _build_messages(source, candidate)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_system_prompt_contains_validation_instructions(self) -> None:
        messages = _build_messages(_make_source_record(), _make_candidate_record())

        system_content = messages[0]["content"]
        assert "validate" in system_content.lower()
        assert "accepted" in system_content
        assert "JSON" in system_content

    def test_user_prompt_contains_source_and_candidate_data(self) -> None:
        source = _make_source_record(isbn="9780306406157", language="es")
        candidate = _make_candidate_record(
            isbn="9780306406157",
            title="Test Title",
            author="Test Author",
            editorial="Test Editorial",
            synopsis="A test synopsis.",
        )

        messages = _build_messages(source, candidate)
        user_content = messages[1]["content"]

        # Source data present
        assert "9780306406157" in user_content
        assert "google_books" in user_content
        assert "es" in user_content
        assert "Fiction" in user_content

        # Candidate data present
        assert "Test Title" in user_content
        assert "Test Author" in user_content
        assert "Test Editorial" in user_content
        assert "A test synopsis." in user_content

    def test_handles_none_optional_fields(self) -> None:
        source = _make_source_record(language=None)
        candidate = _make_candidate_record(subtitle=None, synopsis=None)

        messages = _build_messages(source, candidate)
        user_content = messages[1]["content"]

        # Should not crash; empty strings used for None values
        assert "Source language: " in user_content
        assert "Subtitle: " in user_content


# ---------------------------------------------------------------------------
# _extract_output_text
# ---------------------------------------------------------------------------


class TestExtractOutputText:
    def test_extracts_from_output_text_field(self) -> None:
        payload = {"output_text": '{"accepted": true, "confidence": 0.95}'}
        result = _extract_output_text(payload)
        assert result == '{"accepted": true, "confidence": 0.95}'

    def test_extracts_from_nested_output_content_blocks(self) -> None:
        payload = {
            "output": [
                {
                    "content": [
                        {"text": '{"accepted": true, "confidence": 0.9}'},
                    ]
                }
            ]
        }
        result = _extract_output_text(payload)
        assert result == '{"accepted": true, "confidence": 0.9}'

    def test_concatenates_multiple_text_blocks(self) -> None:
        payload = {
            "output": [
                {
                    "content": [
                        {"text": "first part"},
                        {"text": "second part"},
                    ]
                }
            ]
        }
        result = _extract_output_text(payload)
        assert result == "first part\nsecond part"

    def test_returns_none_for_empty_payload(self) -> None:
        assert _extract_output_text({}) is None

    def test_returns_none_when_output_text_is_whitespace(self) -> None:
        assert _extract_output_text({"output_text": "   "}) is None

    def test_returns_none_when_output_is_not_list(self) -> None:
        assert _extract_output_text({"output": "not a list"}) is None

    def test_skips_non_dict_items_in_output(self) -> None:
        payload = {"output": ["string_item", {"content": [{"text": "valid"}]}]}
        result = _extract_output_text(payload)
        assert result == "valid"

    def test_skips_non_dict_content_items(self) -> None:
        payload = {"output": [{"content": ["not_a_dict", {"text": "valid"}]}]}
        result = _extract_output_text(payload)
        assert result == "valid"

    def test_skips_items_without_content_list(self) -> None:
        payload = {"output": [{"content": "not_a_list"}, {"content": [{"text": "ok"}]}]}
        result = _extract_output_text(payload)
        assert result == "ok"

    def test_prefers_output_text_over_nested_output(self) -> None:
        payload = {
            "output_text": "direct text",
            "output": [{"content": [{"text": "nested text"}]}],
        }
        result = _extract_output_text(payload)
        assert result == "direct text"


# ---------------------------------------------------------------------------
# _parse_validation_response
# ---------------------------------------------------------------------------


class TestParseValidationResponse:
    def test_valid_json_accepted_true(self) -> None:
        text = json.dumps(
            {
                "accepted": True,
                "confidence": 0.95,
                "issues": [],
                "explanation": "All fields are well supported.",
            }
        )
        result = _parse_validation_response(text)

        assert result is not None
        assert result.accepted is True
        assert result.confidence == 0.95
        assert result.issues == []
        assert result.explanation == "All fields are well supported."

    def test_valid_json_accepted_false_with_issues(self) -> None:
        text = json.dumps(
            {
                "accepted": False,
                "confidence": 0.4,
                "issues": ["author_mismatch", "title_suspicious"],
                "explanation": "Author does not match source evidence.",
            }
        )
        result = _parse_validation_response(text)

        assert result is not None
        assert result.accepted is False
        assert result.confidence == 0.4
        assert result.issues == ["author_mismatch", "title_suspicious"]
        assert result.explanation == "Author does not match source evidence."

    def test_json_embedded_in_markdown_code_block(self) -> None:
        text = (
            '```json\n{"accepted": true, "confidence": 0.9,'
            ' "issues": [], "explanation": "OK"}\n```'
        )
        result = _parse_validation_response(text)

        assert result is not None
        assert result.accepted is True
        assert result.confidence == 0.9

    def test_invalid_json_returns_none(self) -> None:
        result = _parse_validation_response("this is not json at all")
        assert result is None

    def test_non_boolean_accepted_returns_none(self) -> None:
        text = json.dumps({"accepted": "yes", "confidence": 0.9, "issues": []})
        result = _parse_validation_response(text)
        assert result is None

    def test_accepted_as_integer_returns_none(self) -> None:
        text = json.dumps({"accepted": 1, "confidence": 0.9, "issues": []})
        result = _parse_validation_response(text)
        assert result is None

    def test_missing_confidence_defaults_to_zero(self) -> None:
        text = json.dumps({"accepted": True, "issues": []})
        result = _parse_validation_response(text)

        assert result is not None
        assert result.confidence == 0.0

    def test_non_numeric_confidence_defaults_to_zero(self) -> None:
        text = json.dumps({"accepted": True, "confidence": "high", "issues": []})
        result = _parse_validation_response(text)

        assert result is not None
        assert result.confidence == 0.0

    def test_non_list_issues_defaults_to_empty(self) -> None:
        text = json.dumps({"accepted": True, "confidence": 0.9, "issues": "none"})
        result = _parse_validation_response(text)

        assert result is not None
        assert result.issues == []

    def test_missing_explanation_defaults_to_none(self) -> None:
        text = json.dumps({"accepted": True, "confidence": 0.9, "issues": []})
        result = _parse_validation_response(text)

        assert result is not None
        assert result.explanation is None

    def test_non_string_explanation_becomes_none(self) -> None:
        text = json.dumps(
            {"accepted": True, "confidence": 0.9, "issues": [], "explanation": 42}
        )
        result = _parse_validation_response(text)

        assert result is not None
        assert result.explanation is None

    def test_whitespace_issues_are_filtered(self) -> None:
        text = json.dumps(
            {"accepted": False, "confidence": 0.5, "issues": ["real_issue", "", "  "]}
        )
        result = _parse_validation_response(text)

        assert result is not None
        assert result.issues == ["real_issue"]

    def test_json_array_returns_none(self) -> None:
        result = _parse_validation_response("[1, 2, 3]")
        assert result is None

    def test_explanation_is_stripped(self) -> None:
        text = json.dumps(
            {
                "accepted": True,
                "confidence": 0.9,
                "issues": [],
                "explanation": "  padded explanation  ",
            }
        )
        result = _parse_validation_response(text)

        assert result is not None
        assert result.explanation == "padded explanation"


# ---------------------------------------------------------------------------
# OpenAIBibliographicValidator._call_api
# ---------------------------------------------------------------------------


class TestCallApi:
    @patch("book_store_assistant.resolution.openai_bibliographic_validator.httpx.post")
    def test_successful_api_call(self, mock_post: MagicMock) -> None:
        response_body = {
            "output_text": json.dumps(
                {
                    "accepted": True,
                    "confidence": 0.95,
                    "issues": [],
                    "explanation": "Looks good.",
                }
            )
        }
        mock_response = MagicMock()
        mock_response.json.return_value = response_body
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        validator = _make_validator()
        result = validator._call_api(_make_source_record(), _make_candidate_record())

        assert result is not None
        assert result.accepted is True
        assert result.confidence == 0.95

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "/responses" in call_kwargs.args[0] or "/responses" in call_kwargs[0][0]

    @patch("book_store_assistant.resolution.openai_bibliographic_validator.httpx.post")
    def test_http_error_returns_none(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = httpx.HTTPError("Connection error")

        validator = _make_validator()
        result = validator._call_api(_make_source_record(), _make_candidate_record())

        assert result is None

    @patch("book_store_assistant.resolution.openai_bibliographic_validator.httpx.post")
    def test_raise_for_status_error_returns_none(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error",
            request=MagicMock(),
            response=MagicMock(),
        )
        mock_post.return_value = mock_response

        validator = _make_validator()
        result = validator._call_api(_make_source_record(), _make_candidate_record())

        assert result is None

    @patch("book_store_assistant.resolution.openai_bibliographic_validator.httpx.post")
    def test_empty_output_text_returns_none(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"output_text": ""}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        validator = _make_validator()
        result = validator._call_api(_make_source_record(), _make_candidate_record())

        assert result is None

    @patch("book_store_assistant.resolution.openai_bibliographic_validator.httpx.post")
    def test_api_url_constructed_correctly(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output_text": json.dumps({"accepted": True, "confidence": 0.9, "issues": []})
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        validator = _make_validator(base_url="https://custom.api.com/v1/")
        validator._call_api(_make_source_record(), _make_candidate_record())

        url_arg = mock_post.call_args[0][0]
        assert url_arg == "https://custom.api.com/v1/responses"

    @patch("book_store_assistant.resolution.openai_bibliographic_validator.httpx.post")
    def test_api_sends_correct_headers_and_model(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output_text": json.dumps({"accepted": True, "confidence": 0.9, "issues": []})
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        validator = _make_validator(api_key="sk-my-key", model="gpt-4o")
        validator._call_api(_make_source_record(), _make_candidate_record())

        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer sk-my-key"
        assert call_kwargs["json"]["model"] == "gpt-4o"


# ---------------------------------------------------------------------------
# OpenAIBibliographicValidator.validate
# ---------------------------------------------------------------------------


class TestValidate:
    @patch("book_store_assistant.resolution.openai_bibliographic_validator.httpx.post")
    def test_accepted_high_confidence_returned_as_is(self, mock_post: MagicMock) -> None:
        response_body = {
            "output_text": json.dumps(
                {"accepted": True, "confidence": 0.95, "issues": [], "explanation": "OK"}
            )
        }
        mock_response = MagicMock()
        mock_response.json.return_value = response_body
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        validator = _make_validator(min_confidence=0.8)
        result = validator.validate(_make_source_record(), _make_candidate_record())

        assert result is not None
        assert result.accepted is True
        assert result.confidence == 0.95
        assert "validator_low_confidence" not in result.issues

    @patch("book_store_assistant.resolution.openai_bibliographic_validator.httpx.post")
    def test_accepted_low_confidence_adds_warning(self, mock_post: MagicMock) -> None:
        response_body = {
            "output_text": json.dumps(
                {"accepted": True, "confidence": 0.5, "issues": [], "explanation": "Uncertain"}
            )
        }
        mock_response = MagicMock()
        mock_response.json.return_value = response_body
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        validator = _make_validator(min_confidence=0.8)
        result = validator.validate(_make_source_record(), _make_candidate_record())

        assert result is not None
        assert result.accepted is True
        assert "validator_low_confidence" in result.issues

    @patch("book_store_assistant.resolution.openai_bibliographic_validator.httpx.post")
    def test_rejected_low_confidence_adds_warning(self, mock_post: MagicMock) -> None:
        response_body = {
            "output_text": json.dumps(
                {
                    "accepted": False,
                    "confidence": 0.3,
                    "issues": ["title_mismatch"],
                    "explanation": "Rejected",
                }
            )
        }
        mock_response = MagicMock()
        mock_response.json.return_value = response_body
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        validator = _make_validator(min_confidence=0.8)
        result = validator.validate(_make_source_record(), _make_candidate_record())

        assert result is not None
        assert result.accepted is False
        assert "validator_low_confidence" in result.issues
        assert "title_mismatch" in result.issues

    @patch("book_store_assistant.resolution.openai_bibliographic_validator.httpx.post")
    def test_rejected_high_confidence_returned_as_is(self, mock_post: MagicMock) -> None:
        response_body = {
            "output_text": json.dumps(
                {
                    "accepted": False,
                    "confidence": 0.95,
                    "issues": ["author_mismatch"],
                    "explanation": "Rejected with high confidence",
                }
            )
        }
        mock_response = MagicMock()
        mock_response.json.return_value = response_body
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        validator = _make_validator(min_confidence=0.8)
        result = validator.validate(_make_source_record(), _make_candidate_record())

        assert result is not None
        assert result.accepted is False
        assert result.issues == ["author_mismatch"]
        assert "validator_low_confidence" not in result.issues

    @patch("book_store_assistant.resolution.openai_bibliographic_validator.time.sleep")
    @patch("book_store_assistant.resolution.openai_bibliographic_validator.httpx.post")
    def test_first_call_none_retry_succeeds(
        self, mock_post: MagicMock, mock_sleep: MagicMock
    ) -> None:
        success_body = {
            "output_text": json.dumps(
                {"accepted": True, "confidence": 0.9, "issues": [], "explanation": "OK"}
            )
        }
        fail_response = MagicMock()
        fail_response.raise_for_status.side_effect = httpx.HTTPError("timeout")

        success_response = MagicMock()
        success_response.json.return_value = success_body
        success_response.raise_for_status.return_value = None

        mock_post.side_effect = [fail_response, success_response]

        validator = _make_validator(timeout_seconds=10.0)
        result = validator.validate(_make_source_record(), _make_candidate_record())

        assert result is not None
        assert result.accepted is True
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(2.0)  # timeout / 5

    @patch("book_store_assistant.resolution.openai_bibliographic_validator.time.sleep")
    @patch("book_store_assistant.resolution.openai_bibliographic_validator.httpx.post")
    def test_both_calls_none_returns_none(
        self, mock_post: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_post.side_effect = httpx.HTTPError("Connection refused")

        validator = _make_validator(timeout_seconds=10.0)
        result = validator.validate(_make_source_record(), _make_candidate_record())

        assert result is None
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once()
