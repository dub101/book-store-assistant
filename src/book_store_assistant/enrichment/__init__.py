from book_store_assistant.enrichment.evidence import (
    DIRECT_SOURCE_RECORD_EVIDENCE,
    SOURCE_PAGE_BODY_DESCRIPTION_EVIDENCE,
    SOURCE_PAGE_META_DESCRIPTION_EVIDENCE,
    SOURCE_PAGE_SCRAPED_EVIDENCE,
    SOURCE_PAGE_STRUCTURED_DATA_EVIDENCE,
    SOURCE_PAGE_STRUCTURED_EVIDENCE,
    SOURCE_SYNOPSIS_EVIDENCE,
    collect_descriptive_evidence,
)
from book_store_assistant.enrichment.generation import (
    MIN_EVIDENCE_CHARACTERS,
    MIN_GENERATED_SYNOPSIS_CHARACTERS,
    has_sufficient_evidence,
    validate_generated_synopsis,
)
from book_store_assistant.enrichment.models import (
    DescriptiveEvidence,
    EnrichmentResult,
    GeneratedSynopsis,
)
from book_store_assistant.enrichment.openai_generator import OpenAISynopsisGenerator
from book_store_assistant.enrichment.page_fetch import (
    HttpPageContentFetcher,
    extract_description_from_html,
)
from book_store_assistant.enrichment.providers import build_default_synopsis_generator
from book_store_assistant.enrichment.service import (
    DefaultSourceRecordEnricher,
    NoOpSourceRecordEnricher,
    enrich_fetch_results,
)

__all__ = [
    "DescriptiveEvidence",
    "EnrichmentResult",
    "GeneratedSynopsis",
    "DefaultSourceRecordEnricher",
    "HttpPageContentFetcher",
    "OpenAISynopsisGenerator",
    "DIRECT_SOURCE_RECORD_EVIDENCE",
    "SOURCE_SYNOPSIS_EVIDENCE",
    "SOURCE_PAGE_BODY_DESCRIPTION_EVIDENCE",
    "SOURCE_PAGE_META_DESCRIPTION_EVIDENCE",
    "SOURCE_PAGE_SCRAPED_EVIDENCE",
    "SOURCE_PAGE_STRUCTURED_DATA_EVIDENCE",
    "SOURCE_PAGE_STRUCTURED_EVIDENCE",
    "MIN_EVIDENCE_CHARACTERS",
    "MIN_GENERATED_SYNOPSIS_CHARACTERS",
    "NoOpSourceRecordEnricher",
    "build_default_synopsis_generator",
    "collect_descriptive_evidence",
    "extract_description_from_html",
    "has_sufficient_evidence",
    "enrich_fetch_results",
    "validate_generated_synopsis",
]
