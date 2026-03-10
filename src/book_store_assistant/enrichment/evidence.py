from book_store_assistant.enrichment.base import PageContentFetcher
from book_store_assistant.enrichment.models import DescriptiveEvidence
from book_store_assistant.enrichment.page_fetch import extract_description_candidates_from_html
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.synopsis import has_synopsis

PAGE_DESCRIPTION_EVIDENCE = "page_description"
SOURCE_SYNOPSIS_EVIDENCE = "source_synopsis"


def collect_descriptive_evidence(
    record: SourceBookRecord,
    page_fetcher: PageContentFetcher | None = None,
) -> list[DescriptiveEvidence]:
    evidence: list[DescriptiveEvidence] = []
    synopsis = record.synopsis

    if has_synopsis(synopsis):
        assert synopsis is not None

        evidence_source = record.field_sources.get("synopsis", record.source_name)
        quality_flags = ["trusted_source_synopsis"]

        if record.language == "es":
            quality_flags.append("spanish_language")
        elif record.language:
            quality_flags.append("non_spanish_language")
        else:
            quality_flags.append("unknown_language")

        evidence.append(
            DescriptiveEvidence(
                source_name=evidence_source,
                evidence_type=SOURCE_SYNOPSIS_EVIDENCE,
                text=synopsis.strip(),
                language=record.language,
                quality_flags=quality_flags,
            )
        )

    if not evidence and record.source_url is not None and page_fetcher is not None:
        page_text = page_fetcher.fetch_text(str(record.source_url))
        if page_text:
            for (
                description_kind,
                description,
            ) in extract_description_candidates_from_html(page_text):
                evidence.append(
                    DescriptiveEvidence(
                        source_name=record.field_sources.get("source_url", record.source_name),
                        evidence_type=PAGE_DESCRIPTION_EVIDENCE,
                        text=description,
                        source_url=str(record.source_url),
                        language=record.language,
                        quality_flags=[
                            "trusted_source_page_description",
                            description_kind,
                        ],
                    )
                )

    return evidence
