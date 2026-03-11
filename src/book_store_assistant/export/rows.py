from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.subject_mapping import find_subject_entry_by_description


def _format_field_sources(field_sources: dict[str, str]) -> str | None:
    if not field_sources:
        return None

    return "; ".join(f"{field}={source}" for field, source in sorted(field_sources.items()))


def _format_evidence_origins(enrichment_result) -> str | None:
    if enrichment_result is None or not enrichment_result.evidence:
        return None

    origin_counts: dict[str, int] = {}
    for evidence in enrichment_result.evidence:
        origin_counts[evidence.evidence_origin] = origin_counts.get(evidence.evidence_origin, 0) + 1

    return ", ".join(
        f"{origin}={count}"
        for origin, count in sorted(origin_counts.items())
    )


def build_books_row(record: BookRecord) -> list[str | None]:
    subject_entry = find_subject_entry_by_description(record.subject)

    return [
        record.isbn,
        record.title,
        record.subtitle,
        record.author,
        record.editorial,
        record.synopsis,
        record.subject,
        subject_entry.subject if subject_entry is not None else None,
        str(record.cover_url) if record.cover_url else None,
    ]


def build_review_row(result: ResolutionResult) -> list[str | None]:
    source_record = result.source_record
    enrichment_result = result.enrichment_result
    if source_record is None:
        return [
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            ", ".join(result.reason_codes),
            "; ".join(result.review_details),
        ]

    subject_entry = (
        find_subject_entry_by_description(source_record.subject)
        if source_record.subject is not None
        else None
    )
    cover_url = str(source_record.cover_url) if source_record.cover_url else None
    categories = ", ".join(source_record.categories)
    field_sources = _format_field_sources(source_record.field_sources)
    source_issue_codes = ", ".join(result.source_issue_codes) if result.source_issue_codes else None
    generated_synopsis_flags = (
        ", ".join(enrichment_result.generated_synopsis.validation_flags)
        if enrichment_result is not None and enrichment_result.generated_synopsis is not None
        else None
    )
    generated_synopsis_text = (
        enrichment_result.generated_synopsis.text
        if enrichment_result is not None and enrichment_result.generated_synopsis is not None
        else None
    )
    generated_synopsis_raw = (
        enrichment_result.generated_synopsis.raw_output_text
        if enrichment_result is not None and enrichment_result.generated_synopsis is not None
        else None
    )
    raw_source_payload = source_record.raw_source_payload
    enrichment_status = None
    evidence_count = None
    evidence_origins = None
    if enrichment_result is not None:
        if enrichment_result.applied:
            enrichment_status = "applied"
        else:
            enrichment_status = enrichment_result.skipped_reason or "not_applied"
        evidence_count = str(len(enrichment_result.evidence))
        evidence_origins = _format_evidence_origins(enrichment_result)

    return [
        source_record.isbn,
        source_record.title,
        source_record.subtitle,
        source_record.author,
        source_record.editorial,
        source_record.source_name,
        source_record.language,
        source_record.subject,
        subject_entry.subject if subject_entry is not None else None,
        subject_entry.subject_type if subject_entry is not None else None,
        categories,
        cover_url,
        source_record.synopsis,
        field_sources,
        source_issue_codes,
        enrichment_status,
        evidence_count,
        evidence_origins,
        generated_synopsis_flags,
        generated_synopsis_text,
        generated_synopsis_raw,
        raw_source_payload,
        ", ".join(result.reason_codes),
        "; ".join(result.review_details),
    ]
