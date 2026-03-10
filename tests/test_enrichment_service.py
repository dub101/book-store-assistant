from book_store_assistant.config import ExecutionMode
from book_store_assistant.enrichment.models import EnrichmentResult, GeneratedSynopsis
from book_store_assistant.enrichment.service import AI_SYNOPSIS_SOURCE, enrich_fetch_results
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


class StubEnricher:
    def enrich(self, record: SourceBookRecord) -> EnrichmentResult:
        return EnrichmentResult(
            isbn=record.isbn,
            source_name=record.source_name,
            applied=True,
            generated_synopsis=GeneratedSynopsis(
                text="Resumen generado a partir de evidencia.",
                evidence_indexes=[0],
            ),
        )


def test_enrich_fetch_results_skips_enrichment_in_rules_only_mode() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(source_name="google_books", isbn="9780306406157"),
            errors=[],
        )
    ]

    enriched_fetch_results, enrichment_results = enrich_fetch_results(
        fetch_results,
        mode=ExecutionMode.RULES_ONLY,
    )

    assert enriched_fetch_results == fetch_results
    assert enrichment_results == [
        EnrichmentResult(isbn="9780306406157", skipped_reason="rules_only_mode")
    ]


def test_enrich_fetch_results_applies_generated_synopsis_in_ai_mode() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Example Title",
                author="Example Author",
                editorial="Example Editorial",
            ),
            errors=[],
        )
    ]

    enriched_fetch_results, enrichment_results = enrich_fetch_results(
        fetch_results,
        mode=ExecutionMode.AI_ENRICHED,
        enricher=StubEnricher(),
    )

    assert enriched_fetch_results[0].record is not None
    assert enriched_fetch_results[0].record.synopsis == "Resumen generado a partir de evidencia."
    assert enriched_fetch_results[0].record.language == "es"
    assert enriched_fetch_results[0].record.field_sources["synopsis"] == AI_SYNOPSIS_SOURCE
    assert enrichment_results[0].generated_synopsis is not None
    assert enrichment_results[0].applied is True


def test_enrich_fetch_results_skips_missing_source_records_in_ai_mode() -> None:
    fetch_results = [FetchResult(isbn="9780306406157", record=None, errors=["No match"])]

    enriched_fetch_results, enrichment_results = enrich_fetch_results(
        fetch_results,
        mode=ExecutionMode.AI_ENRICHED,
    )

    assert enriched_fetch_results == fetch_results
    assert enrichment_results == [
        EnrichmentResult(isbn="9780306406157", skipped_reason="no_source_record")
    ]
