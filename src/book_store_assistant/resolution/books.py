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


TITLE_MISSING_ERROR = "Title is missing."
AUTHOR_MISSING_ERROR = "Author is missing."
EDITORIAL_MISSING_ERROR = "Editorial is missing."
SYNOPSIS_MISSING_ERROR = "Synopsis is missing."
SUBJECT_MISSING_ERROR = "Subject is missing."


def _build_missing_field_detail(source_record: SourceBookRecord, field_name: str) -> str:
    source_name = source_record.field_sources.get(field_name)
    if source_name:
        return f"Review detail: {field_name} from {source_name} requires manual review."
    return f"Review detail: no source supplied {field_name}."


def _build_synopsis_review_detail(source_record: SourceBookRecord) -> str:
    synopsis_source = source_record.field_sources.get("synopsis")
    if synopsis_source and source_record.language:
        return f"Review detail: synopsis came from {synopsis_source} with language '{source_record.language}'."
    if synopsis_source:
        return f"Review detail: synopsis came from {synopsis_source}."
    if source_record.language:
        return f"Review detail: synopsis language is '{source_record.language}'."
    return "Review detail: synopsis requires manual language verification."


def _build_subject_review_detail(source_record: SourceBookRecord) -> str:
    subject_source = source_record.field_sources.get("subject")
    if subject_source:
        return f"Review detail: subject from {subject_source} did not resolve to an allowed bookstore subject."

    category_source = source_record.field_sources.get("categories")
    if category_source and source_record.categories:
        return f"Review detail: categories from {category_source} did not resolve to an allowed bookstore subject."

    return "Review detail: no source supplied subject or usable categories."


def _build_review_details(
    source_record: SourceBookRecord,
    missing_title: bool,
    missing_author: bool,
    missing_editorial: bool,
    missing_synopsis: bool,
    synopsis_review_error: str | None,
    missing_subject: bool,
) -> list[str]:
    details: list[str] = []

    if missing_title:
        details.append(_build_missing_field_detail(source_record, "title"))
    if missing_author:
        details.append(_build_missing_field_detail(source_record, "author"))
    if missing_editorial:
        details.append(_build_missing_field_detail(source_record, "editorial"))
    if missing_synopsis:
        details.append(_build_missing_field_detail(source_record, "synopsis"))
    if synopsis_review_error:
        details.append(_build_synopsis_review_detail(source_record))
    if missing_subject:
        details.append(_build_subject_review_detail(source_record))

    return details


def resolve_book_record(
    source_record: SourceBookRecord,
    subjects_path: Path | None = None,
) -> ResolutionResult:
    errors: list[str] = []
    allowed_subjects = get_subjects(subjects_path) if subjects_path is not None else get_subjects()

    resolved_subject = source_record.subject or resolve_subject(source_record.categories, allowed_subjects)
    resolved_synopsis = resolve_synopsis(source_record.synopsis, source_record.language)
    synopsis_review_error = get_synopsis_review_error(source_record.synopsis, source_record.language)

    missing_title = not source_record.title
    missing_author = not source_record.author
    missing_editorial = not source_record.editorial
    missing_synopsis = not resolved_synopsis and synopsis_review_error is None
    missing_subject = not resolved_subject

    if missing_title:
        errors.append(TITLE_MISSING_ERROR)
    if missing_author:
        errors.append(AUTHOR_MISSING_ERROR)
    if missing_editorial:
        errors.append(EDITORIAL_MISSING_ERROR)
    if missing_synopsis:
        errors.append(SYNOPSIS_MISSING_ERROR)
    if synopsis_review_error:
        errors.append(synopsis_review_error)
    if missing_subject:
        errors.append(SUBJECT_MISSING_ERROR)

    if errors:
        errors.extend(
            _build_review_details(
                source_record=source_record,
                missing_title=missing_title,
                missing_author=missing_author,
                missing_editorial=missing_editorial,
                missing_synopsis=missing_synopsis,
                synopsis_review_error=synopsis_review_error,
                missing_subject=missing_subject,
            )
        )
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
