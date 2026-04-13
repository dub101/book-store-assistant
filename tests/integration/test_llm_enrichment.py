from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from book_store_assistant.sources.llm_enrichment import (
    LLMWebEnricher,
    _build_enriched_record,
    _build_enrichment_prompt,
    _format_catalog_for_prompt,
    _load_subject_catalog,
    _match_catalog_subject,
    _needs_enrichment,
    _parse_enrichment_response,
    augment_fetch_results_with_llm_enrichment,
)
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


def _make_result(isbn: str, **kwargs) -> FetchResult:
    record = SourceBookRecord(source_name="google_books", isbn=isbn, **kwargs)
    return FetchResult(isbn=isbn, record=record, errors=[])


def _make_empty_result(isbn: str) -> FetchResult:
    return FetchResult(isbn=isbn, record=None, errors=[])


class TestNeedsEnrichment:
    def test_needs_enrichment_when_record_is_none(self) -> None:
        result = _make_empty_result("9780306406157")
        assert _needs_enrichment(result) is True

    def test_does_not_need_enrichment_when_title_author_editorial_present(self) -> None:
        result = _make_result(
            "9780306406157",
            title="Title",
            author="Author",
            editorial="Editorial",
        )
        assert _needs_enrichment(result) is False

    def test_needs_enrichment_when_editorial_is_missing(self) -> None:
        result = _make_result(
            "9780306406157",
            title="Title",
            author="Author",
        )
        assert _needs_enrichment(result) is True

    def test_needs_enrichment_when_author_is_missing(self) -> None:
        result = _make_result(
            "9780306406157",
            title="Title",
            editorial="Editorial",
        )
        assert _needs_enrichment(result) is True


class TestLoadSubjectCatalog:
    def test_returns_empty_list_when_path_does_not_exist(self, tmp_path: Path) -> None:
        catalog = _load_subject_catalog(tmp_path / "nonexistent.tsv")
        assert catalog == []

    def test_loads_rows_from_tsv(self, tmp_path: Path) -> None:
        tsv = tmp_path / "subjects.tsv"
        tsv.write_text("Subject\tDescription\tSubject_Type\n20\tNOVELA\tL0\n", encoding="utf-8")
        catalog = _load_subject_catalog(tsv)
        assert len(catalog) == 1
        assert catalog[0]["Subject"] == "20"
        assert catalog[0]["Description"] == "NOVELA"


class TestFormatCatalogForPrompt:
    def test_formats_catalog_as_table(self) -> None:
        catalog = [{"Subject": "2000", "Description": "NOVELA", "Subject_Type": "L0"}]
        text = _format_catalog_for_prompt(catalog)
        assert "2000" in text
        assert "NOVELA" in text

    def test_filters_short_codes_from_catalog(self) -> None:
        catalog = [
            {"Subject": "20", "Description": "NOVELA", "Subject_Type": "L0"},
            {"Subject": "2000", "Description": "NOVELA CONTEMPORANEA", "Subject_Type": "L1"},
        ]
        text = _format_catalog_for_prompt(catalog)
        assert "20 |" not in text
        assert "2000" in text
        assert "NOVELA CONTEMPORANEA" in text

    def test_returns_header_even_for_empty_catalog(self) -> None:
        text = _format_catalog_for_prompt([])
        assert "Code" in text


class TestBuildEnrichmentPrompt:
    def test_includes_isbn_in_prompt(self) -> None:
        messages = _build_enrichment_prompt("9780306406157", None, "catalog")
        content = messages[0]["content"]
        assert "9780306406157" in content

    def test_includes_partial_data_when_available(self) -> None:
        partial = SourceBookRecord(
            source_name="google_books",
            isbn="9780306406157",
            title="Partial Title",
            author="Partial Author",
        )
        messages = _build_enrichment_prompt("9780306406157", partial, "catalog")
        content = messages[0]["content"]
        assert "Partial Title" in content
        assert "Partial Author" in content

    def test_includes_spanish_synopsis_instruction(self) -> None:
        messages = _build_enrichment_prompt("9780306406157", None, "catalog")
        content = messages[0]["content"]
        assert "Spanish" in content or "español" in content.lower()


class TestBuildEnrichedRecord:
    def test_returns_none_when_no_useful_data(self) -> None:
        data = {
            "title": None,
            "subtitle": None,
            "author": None,
            "editorial": None,
            "synopsis": None,
            "subject_name": None,
            "subject_code": None,
            "cover_url": None,
        }
        assert _build_enriched_record("9780306406157", data, None) is None

    def test_builds_record_from_data(self) -> None:
        data = {
            "title": "Cien años de soledad",
            "subtitle": None,
            "author": "Gabriel García Márquez",
            "editorial": "Debolsillo",
            "synopsis": "Una novela épica.",
            "subject_name": "NOVELA",
            "subject_code": "20",
            "cover_url": None,
        }
        record = _build_enriched_record("9788497592208", data, None)
        assert record is not None
        assert record.title == "Cien años de soledad"
        assert record.author == "Gabriel García Márquez"
        assert record.editorial == "Debolsillo"
        assert record.synopsis == "Una novela épica."
        assert record.subject == "NOVELA"
        assert record.subject_code == "20"

    def test_preserves_language_from_existing_record(self) -> None:
        existing = SourceBookRecord(
            source_name="google_books", isbn="9780306406157", language="es"
        )
        data = {
            "title": "Title",
            "subtitle": None,
            "author": "Author",
            "editorial": "Editorial",
            "synopsis": "Sinopsis.",
            "subject_name": "NOVELA",
            "subject_code": "20",
            "cover_url": None,
        }
        record = _build_enriched_record("9780306406157", data, existing)
        assert record is not None
        assert record.language == "es"


class TestAugmentFetchResultsWithLLMEnrichment:
    def test_skips_records_that_do_not_need_enrichment(self) -> None:
        result = _make_result(
            "9780306406157",
            title="Title",
            author="Author",
            editorial="Editorial",
        )
        enricher = MagicMock()
        output = augment_fetch_results_with_llm_enrichment([result], enricher)
        enricher.enrich.assert_not_called()
        assert output[0].record == result.record

    def test_calls_enricher_for_incomplete_records(self) -> None:
        result = _make_result("9780306406157", title="Title", author="Author", editorial=None)
        enricher = MagicMock()
        enricher.enrich.return_value = None
        augment_fetch_results_with_llm_enrichment([result], enricher)
        enricher.enrich.assert_called_once_with("9780306406157", result.record)

    def test_merges_enriched_data_into_existing_record(self) -> None:
        result = _make_result("9780306406157", title="Title", author="Author", editorial=None)
        enriched = SourceBookRecord(
            source_name="llm_web_search",
            isbn="9780306406157",
            editorial="Alfaguara",
            synopsis="Sinopsis completa.",
            subject="NOVELA",
            subject_code="20",
        )
        enricher = MagicMock()
        enricher.enrich.return_value = enriched
        output = augment_fetch_results_with_llm_enrichment([result], enricher)
        assert output[0].record is not None
        assert output[0].record.editorial == "Alfaguara"
        assert output[0].record.title == "Title"  # preserved from original

    def test_handles_none_enrichment_gracefully(self) -> None:
        result = _make_result("9780306406157", title="Title", author="Author", editorial=None)
        enricher = MagicMock()
        enricher.enrich.return_value = None
        output = augment_fetch_results_with_llm_enrichment([result], enricher)
        assert output[0].record == result.record


class TestLLMWebEnricherInit:
    def test_loads_catalog_on_init(self, tmp_path: Path) -> None:
        tsv = tmp_path / "subjects.tsv"
        tsv.write_text("Subject\tDescription\tSubject_Type\n2000\tNOVELA\tL0\n", encoding="utf-8")
        enricher = LLMWebEnricher(
            api_key="test",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            timeout_seconds=30.0,
            catalog_path=tsv,
        )
        assert len(enricher.catalog) == 1
        assert "NOVELA" in enricher.catalog_text

    def test_enrich_returns_none_on_http_error(self, tmp_path: Path) -> None:
        tsv = tmp_path / "subjects.tsv"
        tsv.write_text("Subject\tDescription\tSubject_Type\n", encoding="utf-8")
        enricher = LLMWebEnricher(
            api_key="test",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            timeout_seconds=5.0,
            catalog_path=tsv,
        )
        with patch("httpx.post", side_effect=httpx.ConnectError("connection refused")):
            result = enricher.enrich("9780306406157", None)
        assert result is None


# ---------------------------------------------------------------------------
# Tests for _build_enrichment_prompt with partial record having many fields
# ---------------------------------------------------------------------------


class TestBuildEnrichmentPromptPartialFields:
    def test_includes_all_partial_fields_in_prompt(self) -> None:
        partial = SourceBookRecord(
            source_name="google_books",
            isbn="9780306406157",
            title="Partial Title",
            subtitle="Partial Subtitle",
            author="Partial Author",
            editorial="Partial Editorial",
            language="es",
            categories=["Fiction", "Drama"],
        )
        messages = _build_enrichment_prompt("9780306406157", partial, "catalog text")
        content = messages[0]["content"]
        assert "Partial Title" in content
        assert "Partial Subtitle" in content
        assert "Partial Author" in content
        assert "Partial Editorial" in content
        assert "Language: es" in content
        assert "Fiction" in content
        assert "Drama" in content

    def test_none_partial_produces_isbn_only(self) -> None:
        messages = _build_enrichment_prompt("9780306406157", None, "catalog text")
        content = messages[0]["content"]
        assert "ISBN: 9780306406157" in content
        assert "(partial)" not in content


# ---------------------------------------------------------------------------
# Tests for _parse_enrichment_response
# ---------------------------------------------------------------------------


class TestParseEnrichmentResponse:
    def test_extracts_json_from_valid_response(self) -> None:
        response_json = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"title": "Cien anos", "author": "Marquez"}',
                        }
                    ],
                }
            ]
        }
        result = _parse_enrichment_response(response_json)
        assert result is not None
        assert result["title"] == "Cien anos"
        assert result["author"] == "Marquez"

    def test_returns_none_when_no_message_items(self) -> None:
        response_json = {"output": []}
        result = _parse_enrichment_response(response_json)
        assert result is None

    def test_returns_none_when_output_missing(self) -> None:
        response_json = {}
        result = _parse_enrichment_response(response_json)
        assert result is None

    def test_returns_none_for_invalid_json_text(self) -> None:
        response_json = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "{this is not valid json}",
                        }
                    ],
                }
            ]
        }
        result = _parse_enrichment_response(response_json)
        assert result is None

    def test_skips_non_message_output_items(self) -> None:
        response_json = {
            "output": [
                {"type": "web_search_call", "id": "ws_123"},
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"title": "Found It"}',
                        }
                    ],
                },
            ]
        }
        result = _parse_enrichment_response(response_json)
        assert result is not None
        assert result["title"] == "Found It"

    def test_skips_non_output_text_content_blocks(self) -> None:
        response_json = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "refusal", "text": "I cannot help"},
                        {
                            "type": "output_text",
                            "text": '{"title": "Actual Result"}',
                        },
                    ],
                }
            ]
        }
        result = _parse_enrichment_response(response_json)
        assert result is not None
        assert result["title"] == "Actual Result"

    def test_handles_non_dict_output_items(self) -> None:
        response_json = {"output": ["not a dict", 42]}
        result = _parse_enrichment_response(response_json)
        assert result is None


# ---------------------------------------------------------------------------
# Tests for _match_catalog_subject
# ---------------------------------------------------------------------------


_TEST_CATALOG = [
    {"Subject": "2000", "Description": "NOVELA CONTEMPORANEA", "Subject_Type": "L1"},
    {"Subject": "2010", "Description": "THRILLER O NOVELA NEGRA", "Subject_Type": "L1"},
    {"Subject": "2020", "Description": "CLASICOS", "Subject_Type": "L1"},
    {"Subject": "3000", "Description": "LITERATURA LATINOAMERICANA", "Subject_Type": "L1"},
]


class TestMatchCatalogSubject:
    def test_matches_by_code(self) -> None:
        name, code = _match_catalog_subject(None, "2000", _TEST_CATALOG)
        assert code == "2000"
        assert name == "NOVELA CONTEMPORANEA"

    def test_matches_by_exact_name(self) -> None:
        name, code = _match_catalog_subject("CLASICOS", None, _TEST_CATALOG)
        assert code == "2020"
        assert name == "CLASICOS"

    def test_matches_by_substring(self) -> None:
        name, code = _match_catalog_subject("NOVELA NEGRA", None, _TEST_CATALOG)
        assert code == "2010"
        assert name == "THRILLER O NOVELA NEGRA"

    def test_no_match_returns_original(self) -> None:
        name, code = _match_catalog_subject("UNKNOWN SUBJECT", "9999", _TEST_CATALOG)
        assert name == "UNKNOWN SUBJECT"
        assert code == "9999"

    def test_empty_catalog_returns_original(self) -> None:
        name, code = _match_catalog_subject("NOVELA", "2000", [])
        assert name == "NOVELA"
        assert code == "2000"

    def test_none_inputs_with_catalog(self) -> None:
        name, code = _match_catalog_subject(None, None, _TEST_CATALOG)
        assert name is None
        assert code is None

    def test_accent_insensitive_name_match(self) -> None:
        name, code = _match_catalog_subject("CLASICOS", None, _TEST_CATALOG)
        assert code == "2020"
        assert name == "CLASICOS"

    def test_code_match_with_unknown_name_uses_catalog_description(self) -> None:
        name, code = _match_catalog_subject("Whatever", "3000", _TEST_CATALOG)
        assert code == "3000"
        assert name == "LITERATURA LATINOAMERICANA"


# ---------------------------------------------------------------------------
# Tests for _build_enriched_record with catalog matching
# ---------------------------------------------------------------------------


class TestBuildEnrichedRecordWithCatalog:
    def test_catalog_corrects_subject_and_code(self) -> None:
        data = {
            "title": "El tunel",
            "subtitle": None,
            "author": "Ernesto Sabato",
            "editorial": "Seix Barral",
            "synopsis": "Una novela psicologica.",
            "subject_name": "NOVELA NEGRA",
            "subject_code": None,
            "cover_url": None,
        }
        record = _build_enriched_record("9788432228032", data, None, catalog=_TEST_CATALOG)
        assert record is not None
        assert record.subject == "THRILLER O NOVELA NEGRA"
        assert record.subject_code == "2010"

    def test_catalog_code_lookup(self) -> None:
        data = {
            "title": "Don Quijote",
            "subtitle": None,
            "author": "Cervantes",
            "editorial": "Espasa",
            "synopsis": "La obra maestra.",
            "subject_name": None,
            "subject_code": "2020",
            "cover_url": None,
        }
        record = _build_enriched_record("9788467028423", data, None, catalog=_TEST_CATALOG)
        assert record is not None
        assert record.subject == "CLASICOS"
        assert record.subject_code == "2020"

    def test_cover_url_validated(self) -> None:
        data = {
            "title": "Title",
            "subtitle": None,
            "author": "Author",
            "editorial": "Editorial",
            "synopsis": None,
            "subject_name": None,
            "subject_code": None,
            "cover_url": "https://covers.example.com/cover.jpg",
        }
        record = _build_enriched_record("9780306406157", data, None)
        assert record is not None
        assert record.cover_url is not None
        assert "cover.jpg" in str(record.cover_url)
        assert record.field_sources.get("cover_url") == "llm_web_search"
        assert record.field_confidence.get("cover_url") == 0.8

    def test_invalid_cover_url_set_to_none(self) -> None:
        data = {
            "title": "Title",
            "subtitle": None,
            "author": "Author",
            "editorial": "Editorial",
            "synopsis": None,
            "subject_name": None,
            "subject_code": None,
            "cover_url": "not a valid url",
        }
        record = _build_enriched_record("9780306406157", data, None)
        assert record is not None
        assert record.cover_url is None

    def test_preserves_categories_from_existing(self) -> None:
        existing = SourceBookRecord(
            source_name="google_books",
            isbn="9780306406157",
            language="en",
            categories=["Fiction", "Classics"],
        )
        data = {
            "title": "Title",
            "subtitle": None,
            "author": "Author",
            "editorial": "Editorial",
            "synopsis": "Synopsis.",
            "subject_name": None,
            "subject_code": None,
            "cover_url": None,
        }
        record = _build_enriched_record("9780306406157", data, existing)
        assert record is not None
        assert record.language == "en"
        assert record.categories == ["Fiction", "Classics"]


# ---------------------------------------------------------------------------
# Tests for LLMWebEnricher._call_api and enrich retry
# ---------------------------------------------------------------------------


class TestLLMWebEnricherCallApi:
    def test_call_api_success(self, tmp_path: Path) -> None:
        tsv = tmp_path / "subjects.tsv"
        tsv.write_text("Subject\tDescription\tSubject_Type\n", encoding="utf-8")
        enricher = LLMWebEnricher(
            api_key="test",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            timeout_seconds=5.0,
            catalog_path=tsv,
        )
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"title": "Test Title", "author": "Test Author"}',
                        }
                    ],
                }
            ]
        }
        with patch("httpx.post", return_value=mock_response):
            result = enricher._call_api([{"role": "user", "content": "test"}])
        assert result is not None
        assert result["title"] == "Test Title"

    def test_call_api_http_status_error(self, tmp_path: Path) -> None:
        tsv = tmp_path / "subjects.tsv"
        tsv.write_text("Subject\tDescription\tSubject_Type\n", encoding="utf-8")
        enricher = LLMWebEnricher(
            api_key="test",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            timeout_seconds=5.0,
            catalog_path=tsv,
        )
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error",
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
            response=httpx.Response(500),
        )
        with patch("httpx.post", return_value=mock_response):
            result = enricher._call_api([{"role": "user", "content": "test"}])
        assert result is None

    def test_enrich_retries_on_first_failure(self, tmp_path: Path) -> None:
        tsv = tmp_path / "subjects.tsv"
        tsv.write_text("Subject\tDescription\tSubject_Type\n", encoding="utf-8")
        enricher = LLMWebEnricher(
            api_key="test",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            timeout_seconds=0.1,
            catalog_path=tsv,
        )

        call_count = 0
        mock_success_response = MagicMock()
        mock_success_response.raise_for_status = MagicMock()
        mock_success_response.json.return_value = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": (
                                '{"title": "Retry Title", "subtitle": null,'
                                ' "author": "Author", "editorial": "Ed",'
                                ' "synopsis": null, "subject_name": null,'
                                ' "subject_code": null, "cover_url": null}'
                            ),
                        }
                    ],
                }
            ]
        }

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("connection refused")
            return mock_success_response

        with patch("httpx.post", side_effect=side_effect), patch("time.sleep"):
            result = enricher.enrich("9780306406157", None)

        assert call_count == 2
        assert result is not None
        assert result.title == "Retry Title"

    def test_enrich_returns_none_after_both_failures(self, tmp_path: Path) -> None:
        tsv = tmp_path / "subjects.tsv"
        tsv.write_text("Subject\tDescription\tSubject_Type\n", encoding="utf-8")
        enricher = LLMWebEnricher(
            api_key="test",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            timeout_seconds=0.1,
            catalog_path=tsv,
        )
        with (
            patch("httpx.post", side_effect=httpx.ConnectError("refused")),
            patch("time.sleep"),
        ):
            result = enricher.enrich("9780306406157", None)
        assert result is None


# ---------------------------------------------------------------------------
# Tests for augment_fetch_results_with_llm_enrichment
# ---------------------------------------------------------------------------


class TestAugmentFetchResultsExtended:
    def test_enricher_merge_adds_diagnostic(self) -> None:
        result = _make_result("9780306406157", title="Title", author="Author")
        enriched = SourceBookRecord(
            source_name="llm_web_search",
            isbn="9780306406157",
            editorial="LLM Editorial",
            synopsis="LLM Synopsis",
        )
        enricher = MagicMock()
        enricher.enrich.return_value = enriched
        output = augment_fetch_results_with_llm_enrichment([result], enricher)

        assert output[0].record is not None
        assert output[0].record.editorial == "LLM Editorial"
        assert output[0].record.title == "Title"
        assert any(
            d.get("action") == "record_updated" for d in output[0].diagnostics
        )

    def test_enricher_returns_none_adds_enrichment_failed_diagnostic(self) -> None:
        result = _make_result("9780306406157", title="Title", author="Author")
        enricher = MagicMock()
        enricher.enrich.return_value = None
        output = augment_fetch_results_with_llm_enrichment([result], enricher)

        assert any(
            d.get("action") == "enrichment_failed" for d in output[0].diagnostics
        )

    def test_skips_complete_records_does_not_call_enricher(self) -> None:
        result = _make_result(
            "9780306406157",
            title="Title",
            author="Author",
            editorial="Editorial",
        )
        enricher = MagicMock()
        output = augment_fetch_results_with_llm_enrichment([result], enricher)
        enricher.enrich.assert_not_called()
        assert output[0].record == result.record
        assert len(output[0].diagnostics) == 0

    def test_enriches_record_with_no_existing_record(self) -> None:
        result = _make_empty_result("9780306406157")
        enriched = SourceBookRecord(
            source_name="llm_web_search",
            isbn="9780306406157",
            title="New Title",
            author="New Author",
            editorial="New Editorial",
        )
        enricher = MagicMock()
        enricher.enrich.return_value = enriched
        output = augment_fetch_results_with_llm_enrichment([result], enricher)

        assert output[0].record is not None
        assert output[0].record.title == "New Title"
        assert output[0].record.author == "New Author"
        assert output[0].record.editorial == "New Editorial"

    def test_on_status_update_callback_called(self) -> None:
        result = _make_result("9780306406157", title="Title")
        enricher = MagicMock()
        enricher.enrich.return_value = None
        status_messages: list[str] = []
        on_status = MagicMock(side_effect=lambda msg: status_messages.append(msg))

        augment_fetch_results_with_llm_enrichment(
            [result], enricher, on_status_update=on_status
        )

        assert on_status.call_count >= 2
        assert any("LLM web enrichment" in msg for msg in status_messages)
        assert any("9780306406157" in msg for msg in status_messages)

    def test_mixed_complete_and_incomplete_records(self) -> None:
        complete = _make_result(
            "9780306406157",
            title="Title",
            author="Author",
            editorial="Editorial",
        )
        incomplete = _make_result("9780451524935", title="Only Title")
        enriched = SourceBookRecord(
            source_name="llm_web_search",
            isbn="9780451524935",
            author="LLM Author",
            editorial="LLM Ed",
        )
        enricher = MagicMock()
        enricher.enrich.return_value = enriched

        output = augment_fetch_results_with_llm_enrichment(
            [complete, incomplete], enricher
        )

        assert len(output) == 2
        enricher.enrich.assert_called_once_with("9780451524935", incomplete.record)
        assert output[0].record.title == "Title"  # unchanged
        assert output[1].record.author == "LLM Author"

    def test_returns_original_when_no_records_need_enrichment(self) -> None:
        r1 = _make_result("9780306406157", title="T", author="A", editorial="E")
        r2 = _make_result("9780451524935", title="T2", author="A2", editorial="E2")
        enricher = MagicMock()

        output = augment_fetch_results_with_llm_enrichment([r1, r2], enricher)

        enricher.enrich.assert_not_called()
        assert output == [r1, r2]
