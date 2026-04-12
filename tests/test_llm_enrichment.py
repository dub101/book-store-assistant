from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from book_store_assistant.sources.llm_enrichment import (
    LLMWebEnricher,
    _build_enriched_record,
    _build_enrichment_prompt,
    _format_catalog_for_prompt,
    _load_subject_catalog,
    _needs_enrichment,
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
