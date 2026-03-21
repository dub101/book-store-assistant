from book_store_assistant.enrichment.base import PageContentFetcher
from book_store_assistant.enrichment.models import DescriptiveEvidence
from book_store_assistant.enrichment.page_fetch import extract_description_candidates_from_html
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.synopsis import has_synopsis

SOURCE_SYNOPSIS_EVIDENCE = "source_synopsis"
SOURCE_TITLE_EVIDENCE = "source_title"
SOURCE_SUBTITLE_EVIDENCE = "source_subtitle"
SOURCE_AUTHOR_EVIDENCE = "source_author"
SOURCE_EDITORIAL_EVIDENCE = "source_editorial"
SOURCE_PAGE_STRUCTURED_DATA_EVIDENCE = "source_page_structured_data"
SOURCE_PAGE_META_DESCRIPTION_EVIDENCE = "source_page_meta_description"
SOURCE_PAGE_BODY_DESCRIPTION_EVIDENCE = "source_page_body_description"

DIRECT_SOURCE_RECORD_EVIDENCE = "direct_source_record"
SOURCE_PAGE_STRUCTURED_EVIDENCE = "source_page_structured"
SOURCE_PAGE_SCRAPED_EVIDENCE = "source_page_scraped"

STRUCTURED_PAGE_DESCRIPTION_KINDS = {
    "structured_data",
    "google_books_embedded_data",
    "open_library_embedded_data",
}
SCRAPED_PAGE_DESCRIPTION_KINDS = {
    "meta_description",
    "body_description",
}


def _build_page_evidence_metadata(description_kind: str) -> tuple[str, str]:
    if description_kind in STRUCTURED_PAGE_DESCRIPTION_KINDS:
        return SOURCE_PAGE_STRUCTURED_DATA_EVIDENCE, SOURCE_PAGE_STRUCTURED_EVIDENCE

    if description_kind == "meta_description":
        return SOURCE_PAGE_META_DESCRIPTION_EVIDENCE, SOURCE_PAGE_SCRAPED_EVIDENCE

    if description_kind == "body_description":
        return SOURCE_PAGE_BODY_DESCRIPTION_EVIDENCE, SOURCE_PAGE_SCRAPED_EVIDENCE

    return SOURCE_PAGE_BODY_DESCRIPTION_EVIDENCE, SOURCE_PAGE_SCRAPED_EVIDENCE


def collect_descriptive_evidence(
    record: SourceBookRecord,
    page_fetcher: PageContentFetcher | None = None,
) -> list[DescriptiveEvidence]:
    evidence: list[DescriptiveEvidence] = []
    seen_evidence_keys: set[tuple[str, str]] = set()

    synopsis_text = record.synopsis or ""
    if has_synopsis(synopsis_text):
        quality_flags = ["trusted_source_synopsis"]
        if record.language == "es":
            quality_flags.append("spanish_language")
        elif record.language:
            quality_flags.append("non_spanish_language")
        else:
            quality_flags.append("unknown_language")
        evidence_item = DescriptiveEvidence(
            source_name=record.field_sources.get("synopsis", record.source_name),
            evidence_type=SOURCE_SYNOPSIS_EVIDENCE,
            evidence_origin=DIRECT_SOURCE_RECORD_EVIDENCE,
            text=synopsis_text.strip(),
            source_url=str(record.source_url) if record.source_url is not None else None,
            language=record.language,
            extraction_method="source_synopsis_field",
            quality_flags=quality_flags,
        )
        key = (
            evidence_item.evidence_type,
            evidence_item.text.casefold(),
        )
        if key not in seen_evidence_keys:
            seen_evidence_keys.add(key)
            evidence.append(evidence_item)

    direct_field_evidence_types = {
        "title": SOURCE_TITLE_EVIDENCE,
        "subtitle": SOURCE_SUBTITLE_EVIDENCE,
        "author": SOURCE_AUTHOR_EVIDENCE,
        "editorial": SOURCE_EDITORIAL_EVIDENCE,
    }

    for field_name, evidence_type in direct_field_evidence_types.items():
        field_value = getattr(record, field_name)
        if not isinstance(field_value, str) or not field_value.strip():
            continue

        evidence_item = DescriptiveEvidence(
            source_name=record.field_sources.get(field_name, record.source_name),
            evidence_type=evidence_type,
            evidence_origin=DIRECT_SOURCE_RECORD_EVIDENCE,
            text=field_value,
            source_url=str(record.source_url) if record.source_url is not None else None,
            language=record.language if field_name == "subtitle" else None,
            extraction_method=f"source_{field_name}_field",
            quality_flags=["trusted_source_bibliographic_field", field_name],
        )
        key = (
            evidence_item.evidence_type,
            evidence_item.text.casefold(),
        )
        if key in seen_evidence_keys:
            continue
        seen_evidence_keys.add(key)
        evidence.append(evidence_item)

    has_descriptive_evidence = any(
        item.evidence_type != SOURCE_TITLE_EVIDENCE
        and item.evidence_type != SOURCE_SUBTITLE_EVIDENCE
        and item.evidence_type != SOURCE_AUTHOR_EVIDENCE
        and item.evidence_type != SOURCE_EDITORIAL_EVIDENCE
        for item in evidence
    )

    if not has_descriptive_evidence and record.source_url is not None and page_fetcher is not None:
        page_text = page_fetcher.fetch_text(str(record.source_url))
        if page_text:
            for (
                description_kind,
                description,
            ) in extract_description_candidates_from_html(
                page_text,
                source_url=str(record.source_url),
            ):
                evidence_type, evidence_origin = _build_page_evidence_metadata(description_kind)
                evidence.append(
                    DescriptiveEvidence(
                        source_name=record.field_sources.get("source_url", record.source_name),
                        evidence_type=evidence_type,
                        evidence_origin=evidence_origin,
                        text=description,
                        source_url=str(record.source_url),
                        language=record.language,
                        extraction_method=description_kind,
                        quality_flags=[
                            "trusted_source_page_description",
                            description_kind,
                        ],
                    )
                )

    return evidence
