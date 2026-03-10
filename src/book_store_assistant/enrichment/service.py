from book_store_assistant.config import ExecutionMode
from book_store_assistant.enrichment.base import SourceRecordEnricher
from book_store_assistant.enrichment.models import EnrichmentResult
from book_store_assistant.sources.results import FetchResult

AI_SYNOPSIS_SOURCE = "ai_enriched"


class NoOpSourceRecordEnricher:
    def enrich(self, record) -> EnrichmentResult:
        return EnrichmentResult(
            isbn=record.isbn,
            source_name=record.source_name,
            applied=False,
            skipped_reason="no_enrichment_available",
        )


def _apply_generated_synopsis(
    fetch_result: FetchResult,
    enrichment_result: EnrichmentResult,
) -> FetchResult:
    if fetch_result.record is None or enrichment_result.generated_synopsis is None:
        return fetch_result

    if fetch_result.record.synopsis:
        return fetch_result

    enriched_field_sources = dict(fetch_result.record.field_sources)
    enriched_field_sources["synopsis"] = AI_SYNOPSIS_SOURCE

    enriched_record = fetch_result.record.model_copy(
        update={
            "synopsis": enrichment_result.generated_synopsis.text,
            "language": enrichment_result.generated_synopsis.language,
            "field_sources": enriched_field_sources,
        }
    )
    return fetch_result.model_copy(update={"record": enriched_record})


def enrich_fetch_results(
    fetch_results: list[FetchResult],
    mode: ExecutionMode,
    enricher: SourceRecordEnricher | None = None,
) -> tuple[list[FetchResult], list[EnrichmentResult]]:
    if mode is ExecutionMode.RULES_ONLY:
        return (
            fetch_results,
            [
                EnrichmentResult(isbn=fetch_result.isbn, skipped_reason="rules_only_mode")
                for fetch_result in fetch_results
            ],
        )

    active_enricher = enricher or NoOpSourceRecordEnricher()
    enriched_fetch_results: list[FetchResult] = []
    enrichment_results: list[EnrichmentResult] = []

    for fetch_result in fetch_results:
        if fetch_result.record is None:
            enriched_fetch_results.append(fetch_result)
            enrichment_results.append(
                EnrichmentResult(
                    isbn=fetch_result.isbn,
                    skipped_reason="no_source_record",
                )
            )
            continue

        enrichment_result = active_enricher.enrich(fetch_result.record)
        enrichment_results.append(enrichment_result)
        enriched_fetch_results.append(_apply_generated_synopsis(fetch_result, enrichment_result))

    return enriched_fetch_results, enrichment_results
