from collections.abc import Callable

from book_store_assistant.config import ExecutionMode
from book_store_assistant.enrichment.base import (
    PageContentFetcher,
    SourceRecordEnricher,
    SynopsisGenerator,
)
from book_store_assistant.enrichment.evidence import collect_descriptive_evidence
from book_store_assistant.enrichment.generation import (
    has_sufficient_evidence,
    validate_generated_synopsis,
)
from book_store_assistant.enrichment.models import EnrichmentResult
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult

AI_SYNOPSIS_SOURCE = "ai_enriched"
EnrichmentStartCallback = Callable[[int, int, str], None]
EnrichmentCompleteCallback = Callable[[int, int, EnrichmentResult], None]


class NoOpSourceRecordEnricher:
    def __init__(self, page_fetcher: PageContentFetcher | None = None) -> None:
        self.page_fetcher = page_fetcher

    def enrich(self, record: SourceBookRecord) -> EnrichmentResult:
        evidence = collect_descriptive_evidence(record, page_fetcher=self.page_fetcher)
        skipped_reason = "existing_synopsis_present" if evidence else "insufficient_evidence"

        return EnrichmentResult(
            isbn=record.isbn,
            source_name=record.source_name,
            applied=False,
            skipped_reason=skipped_reason,
            evidence=evidence,
        )


class DefaultSourceRecordEnricher:
    def __init__(
        self,
        generator: SynopsisGenerator | None = None,
        page_fetcher: PageContentFetcher | None = None,
    ) -> None:
        self.generator = generator
        self.page_fetcher = page_fetcher

    def enrich(self, record: SourceBookRecord) -> EnrichmentResult:
        evidence = collect_descriptive_evidence(record, page_fetcher=self.page_fetcher)

        if not has_sufficient_evidence(evidence):
            return EnrichmentResult(
                isbn=record.isbn,
                source_name=record.source_name,
                applied=False,
                skipped_reason="insufficient_evidence",
                evidence=evidence,
            )

        if self.generator is None:
            return EnrichmentResult(
                isbn=record.isbn,
                source_name=record.source_name,
                applied=False,
                skipped_reason="no_generator_configured",
                evidence=evidence,
            )

        generated_synopsis = self.generator.generate(record.isbn, evidence)
        if generated_synopsis is None:
            return EnrichmentResult(
                isbn=record.isbn,
                source_name=record.source_name,
                applied=False,
                skipped_reason="generator_returned_no_synopsis",
                evidence=evidence,
            )

        validation_flags = validate_generated_synopsis(generated_synopsis, evidence)
        if validation_flags:
            return EnrichmentResult(
                isbn=record.isbn,
                source_name=record.source_name,
                applied=False,
                skipped_reason="generated_synopsis_rejected",
                evidence=evidence,
                generated_synopsis=generated_synopsis.model_copy(
                    update={"validation_flags": validation_flags}
                ),
            )

        return EnrichmentResult(
            isbn=record.isbn,
            source_name=record.source_name,
            applied=True,
            evidence=evidence,
            generated_synopsis=generated_synopsis,
        )


def _normalize_enrichment_result(
    record: SourceBookRecord,
    enrichment_result: EnrichmentResult,
) -> EnrichmentResult:
    if enrichment_result.evidence:
        return enrichment_result

    fallback_evidence = collect_descriptive_evidence(record)
    if fallback_evidence:
        return enrichment_result.model_copy(update={"evidence": fallback_evidence})

    return enrichment_result
def _apply_generated_synopsis(
    fetch_result: FetchResult,
    enrichment_result: EnrichmentResult,
) -> FetchResult:
    if (
        fetch_result.record is None
        or enrichment_result.generated_synopsis is None
        or not enrichment_result.applied
    ):
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
    generator: SynopsisGenerator | None = None,
    page_fetcher: PageContentFetcher | None = None,
    on_enrichment_start: EnrichmentStartCallback | None = None,
    on_enrichment_complete: EnrichmentCompleteCallback | None = None,
) -> tuple[list[FetchResult], list[EnrichmentResult]]:
    if mode is ExecutionMode.RULES_ONLY:
        return (
            fetch_results,
            [
                EnrichmentResult(isbn=fetch_result.isbn, skipped_reason="rules_only_mode")
                for fetch_result in fetch_results
            ],
        )

    active_enricher = enricher or DefaultSourceRecordEnricher(
        generator=generator,
        page_fetcher=page_fetcher,
    )
    enriched_fetch_results: list[FetchResult] = []
    enrichment_results: list[EnrichmentResult] = []
    total = len(fetch_results)

    for index, fetch_result in enumerate(fetch_results, start=1):
        if on_enrichment_start is not None:
            on_enrichment_start(index, total, fetch_result.isbn)

        if fetch_result.record is None:
            enrichment_result = EnrichmentResult(
                isbn=fetch_result.isbn,
                skipped_reason="no_source_record",
            )
            enriched_fetch_results.append(fetch_result)
            enrichment_results.append(enrichment_result)
            if on_enrichment_complete is not None:
                on_enrichment_complete(index, total, enrichment_result)
            continue

        enrichment_result = _normalize_enrichment_result(
            fetch_result.record,
            active_enricher.enrich(fetch_result.record),
        )
        enrichment_results.append(enrichment_result)
        enriched_fetch_results.append(_apply_generated_synopsis(fetch_result, enrichment_result))
        if on_enrichment_complete is not None:
            on_enrichment_complete(index, total, enrichment_result)

    return enriched_fetch_results, enrichment_results
