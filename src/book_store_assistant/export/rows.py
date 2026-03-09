from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.subject_mapping import find_subject_entry_by_description


def _format_field_sources(field_sources: dict[str, str]) -> str | None:
    if not field_sources:
        return None

    return "; ".join(f"{field}={source}" for field, source in sorted(field_sources.items()))


def build_books_row(record: BookRecord) -> list[str | None]:
    return [
        record.isbn,
        record.title,
        record.subtitle,
        record.author,
        record.editorial,
        record.synopsis,
        record.subject,
        str(record.cover_url) if record.cover_url else None,
    ]


def build_review_row(result: ResolutionResult) -> list[str | None]:
    source_record = result.source_record
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
        ", ".join(result.reason_codes),
        "; ".join(result.review_details),
    ]
