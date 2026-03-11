from book_store_assistant.config import ExecutionMode
from book_store_assistant.enrichment.evidence import SOURCE_SYNOPSIS_EVIDENCE
from book_store_assistant.enrichment.models import EnrichmentResult, GeneratedSynopsis
from book_store_assistant.enrichment.service import AI_SYNOPSIS_SOURCE, enrich_fetch_results
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult

LONG_EXISTING_SYNOPSIS = (
    "Descripcion del libro lo bastante extensa para servir como evidencia suficiente "
    "y permitir una estandarizacion conservadora del resumen final."
)


class StubEnricher:
    def enrich(self, record: SourceBookRecord) -> EnrichmentResult:
        return EnrichmentResult(
            isbn=record.isbn,
            source_name=record.source_name,
            applied=True,
            generated_synopsis=GeneratedSynopsis(
                text="Resumen generado a partir de evidencia suficiente para su aceptacion.",
                evidence_indexes=[0],
            ),
        )


class StubGenerator:
    def __init__(self, synopsis: GeneratedSynopsis | None) -> None:
        self.synopsis = synopsis

    def generate(self, isbn: str, evidence) -> GeneratedSynopsis | None:
        return self.synopsis


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


def test_enrich_fetch_results_reports_progress_callbacks_for_each_item() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                synopsis="Descripcion del libro.",
                language="es",
                field_sources={"synopsis": "google_books"},
            ),
            errors=[],
        ),
        FetchResult(
            isbn="9780306406158",
            record=None,
            errors=["No match"],
        ),
    ]
    starts: list[tuple[int, int, str]] = []
    completes: list[tuple[int, int, str]] = []

    def on_enrichment_start(index: int, total: int, isbn: str) -> None:
        starts.append((index, total, isbn))

    def on_enrichment_complete(index: int, total: int, result: EnrichmentResult) -> None:
        completes.append((index, total, result.isbn))

    enrich_fetch_results(
        fetch_results,
        mode=ExecutionMode.AI_ENRICHED,
        on_enrichment_start=on_enrichment_start,
        on_enrichment_complete=on_enrichment_complete,
    )

    assert starts == [
        (1, 2, "9780306406157"),
        (2, 2, "9780306406158"),
    ]
    assert completes == [
        (1, 2, "9780306406157"),
        (2, 2, "9780306406158"),
    ]


def test_enrich_fetch_results_collects_existing_synopsis_evidence_in_ai_mode() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books + open_library",
                isbn="9780306406157",
                synopsis=LONG_EXISTING_SYNOPSIS,
                language="es",
                field_sources={"synopsis": "open_library"},
            ),
            errors=[],
        )
    ]

    enriched_fetch_results, enrichment_results = enrich_fetch_results(
        fetch_results,
        mode=ExecutionMode.AI_ENRICHED,
    )

    assert enriched_fetch_results == fetch_results
    assert enrichment_results[0].skipped_reason == "no_generator_configured"
    assert len(enrichment_results[0].evidence) == 1
    assert enrichment_results[0].evidence[0].source_name == "open_library"
    assert enrichment_results[0].evidence[0].evidence_type == SOURCE_SYNOPSIS_EVIDENCE
    assert enrichment_results[0].evidence[0].evidence_origin == "direct_source_record"
    assert enrichment_results[0].evidence[0].text == LONG_EXISTING_SYNOPSIS
    assert enrichment_results[0].evidence[0].language == "es"
    assert enrichment_results[0].evidence[0].extraction_method == "source_synopsis_field"
    assert enrichment_results[0].evidence[0].quality_flags == [
        "trusted_source_synopsis",
        "spanish_language",
    ]


def test_enrich_fetch_results_standardizes_existing_spanish_synopsis_when_generator_is_available(
) -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                synopsis=LONG_EXISTING_SYNOPSIS,
                language="es",
                field_sources={"synopsis": "google_books"},
            ),
            errors=[],
        )
    ]
    generated = GeneratedSynopsis(
        text="Resumen generado a partir de evidencia textual suficiente y trazable del origen.",
        evidence_indexes=[0],
    )

    enriched_fetch_results, enrichment_results = enrich_fetch_results(
        fetch_results,
        mode=ExecutionMode.AI_ENRICHED,
        generator=StubGenerator(generated),
    )

    assert enriched_fetch_results[0].record is not None
    assert enriched_fetch_results[0].record.synopsis == generated.text
    assert enriched_fetch_results[0].record.language == "es"
    assert enriched_fetch_results[0].record.field_sources["synopsis"] == AI_SYNOPSIS_SOURCE
    assert enrichment_results[0].applied is True


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
    assert enriched_fetch_results[0].record.synopsis == (
        "Resumen generado a partir de evidencia suficiente para su aceptacion."
    )
    assert enriched_fetch_results[0].record.language == "es"
    assert enriched_fetch_results[0].record.field_sources["synopsis"] == AI_SYNOPSIS_SOURCE
    assert enrichment_results[0].generated_synopsis is not None
    assert enrichment_results[0].applied is True


def test_enrich_fetch_results_uses_generator_for_non_spanish_synopsis() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                synopsis=(
                    "This detailed source description provides enough grounded evidence to produce "
                    "a Spanish synopsis without inventing metadata."
                ),
                language="en",
            ),
            errors=[],
        )
    ]

    generated = GeneratedSynopsis(
        text="Resumen generado a partir de evidencia textual suficiente y trazable del origen.",
        evidence_indexes=[0],
    )

    enriched_fetch_results, enrichment_results = enrich_fetch_results(
        fetch_results,
        mode=ExecutionMode.AI_ENRICHED,
        generator=StubGenerator(generated),
    )

    assert enriched_fetch_results[0].record is not None
    assert enriched_fetch_results[0].record.synopsis == generated.text
    assert enriched_fetch_results[0].record.language == "es"
    assert enrichment_results[0].applied is True


def test_enrich_fetch_results_rejects_invalid_generated_synopsis() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                synopsis=(
                    "This detailed source description provides enough grounded evidence to produce "
                    "a Spanish synopsis without inventing metadata."
                ),
                language="en",
            ),
            errors=[],
        )
    ]

    enriched_fetch_results, enrichment_results = enrich_fetch_results(
        fetch_results,
        mode=ExecutionMode.AI_ENRICHED,
        generator=StubGenerator(
            GeneratedSynopsis(
                text="Too short",
                language="en",
                evidence_indexes=[],
            )
        ),
    )

    assert enriched_fetch_results == fetch_results
    assert enrichment_results[0].applied is False
    assert enrichment_results[0].skipped_reason == "generated_synopsis_rejected"
    assert enrichment_results[0].generated_synopsis is not None
    assert enrichment_results[0].generated_synopsis.validation_flags == [
        "non_spanish_generated_synopsis",
        "generated_synopsis_too_short",
        "missing_evidence_references",
    ]


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


def test_enrich_fetch_results_marks_insufficient_evidence_when_no_synopsis_exists() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Example Title",
            ),
            errors=[],
        )
    ]

    _, enrichment_results = enrich_fetch_results(
        fetch_results,
        mode=ExecutionMode.AI_ENRICHED,
    )

    assert enrichment_results == [
        EnrichmentResult(
            isbn="9780306406157",
            source_name="google_books",
            applied=False,
            skipped_reason="insufficient_evidence",
            evidence=[
                {
                    "source_name": "google_books",
                    "evidence_type": "source_title",
                    "evidence_origin": "direct_source_record",
                    "text": "Example Title",
                    "source_url": None,
                    "language": None,
                    "extraction_method": "source_title_field",
                    "quality_flags": ["trusted_source_bibliographic_field", "title"],
                }
            ],
        )
    ]


def test_enrich_fetch_results_reports_missing_generator_when_evidence_is_sufficient() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                synopsis=(
                    "This detailed source description provides enough grounded evidence to produce "
                    "a Spanish synopsis without inventing metadata."
                ),
                language="en",
            ),
            errors=[],
        )
    ]

    _, enrichment_results = enrich_fetch_results(
        fetch_results,
        mode=ExecutionMode.AI_ENRICHED,
    )

    assert enrichment_results[0].skipped_reason == "no_generator_configured"


def test_enrich_fetch_results_rejects_generated_synopsis_without_descriptive_evidence_reference(
) -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title=(
                    "Titulo extremadamente largo con suficiente texto para superar el umbral "
                    "de evidencia sin aportar una descripcion real del libro o su argumento"
                ),
            ),
            errors=[],
        )
    ]

    enriched_fetch_results, enrichment_results = enrich_fetch_results(
        fetch_results,
        mode=ExecutionMode.AI_ENRICHED,
        generator=StubGenerator(
            GeneratedSynopsis(
                text="Resumen generado a partir de texto bibliografico insuficiente.",
                evidence_indexes=[0],
            )
        ),
    )

    assert enriched_fetch_results == fetch_results
    assert enrichment_results[0].applied is False
    assert enrichment_results[0].skipped_reason == "generated_synopsis_rejected"
    assert enrichment_results[0].generated_synopsis is not None
    assert enrichment_results[0].generated_synopsis.validation_flags == [
        "insufficient_descriptive_evidence_reference"
    ]
