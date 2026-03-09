from pathlib import Path

from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.resolution.subject_resolution import resolve_subject
from book_store_assistant.resolution.synopsis_resolution import (
    get_synopsis_review_error,
    resolve_synopsis,
)
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.subject_mapping import get_subjects


def resolve_book_record(
    source_record: SourceBookRecord,
    subjects_path: Path | None = None,
) -> ResolutionResult:
    errors: list[str] = []
    allowed_subjects = get_subjects(subjects_path) if subjects_path is not None else get_subjects()

    resolved_subject = source_record.subject or resolve_subject(source_record.categories, allowed_subjects)
    resolved_synopsis = resolve_synopsis(source_record.synopsis, source_record.language)
    synopsis_review_error = get_synopsis_review_error(source_record.synopsis, source_record.language)

    if not source_record.title:
        errors.append("Title is missing.")
    if not source_record.author:
        errors.append("Author is missing.")
    if not source_record.editorial:
        errors.append("Editorial is missing.")
    if not resolved_synopsis and synopsis_review_error is None:
        errors.append("Synopsis is missing.")
    if synopsis_review_error:
        errors.append(synopsis_review_error)
    if not resolved_subject:
        errors.append("Subject is missing.")

    if errors:
        return ResolutionResult(record=None, source_record=source_record, errors=errors)

    record = BookRecord(
        isbn=source_record.isbn,
        title=source_record.title,
        subtitle=source_record.subtitle,
        author=source_record.author,
        editorial=source_record.editorial,
        synopsis=resolved_synopsis,
        subject=resolved_subject,
        cover_url=source_record.cover_url,
    )

    return ResolutionResult(record=record, source_record=source_record, errors=[])
