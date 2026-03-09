from pathlib import Path

from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.resolution.subject_resolution import resolve_subject
from book_store_assistant.resolution.synopsis_resolution import (
    NON_SPANISH_SYNOPSIS_REVIEW_ERROR,
    get_synopsis_review_error,
    resolve_synopsis,
)
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.subject_mapping import get_subject_rows


TITLE_MISSING_ERROR = "Title is missing."
AUTHOR_MISSING_ERROR = "Author is missing."
EDITORIAL_MISSING_ERROR = "Editorial is missing."
SYNOPSIS_MISSING_ERROR = "Synopsis is missing."
SUBJECT_MISSING_ERROR = "Subject is missing."

TITLE_MISSING_CODE = "MISSING_TITLE"
AUTHOR_MISSING_CODE = "MISSING_AUTHOR"
EDITORIAL_MISSING_CODE = "MISSING_EDITORIAL"
SYNOPSIS_MISSING_CODE = "MISSING_SYNOPSIS"
SUBJECT_MISSING_CODE = "MISSING_SUBJECT"
NON_SPANISH_SYNOPSIS_CODE = "NON_SPANISH_SYNOPSIS"


def _build_missing_field_detail(source_record: SourceBookRecord, field_name: str) -> str:
    source_name = source_record.field_sources.get(field_name)
    if source_name:
        return f"{field_name} from {source_name} requires manual review."
    return f"No source supplied {field_name}."


def _build_synopsis_review_detail(source_record: SourceBookRecord) -> str:
    synopsis_source = source_record.field_sources.get("synopsis")
    if synopsis_source and source_record.language:
        return f"Synopsis came from {synopsis_source} with language '{source_record.language}'."
    if synopsis_source:
        return f"Synopsis came from {synopsis_source}."
    if source_record.language:
        return f"Synopsis language is '{source_record.language}'."
    return "Synopsis requires manual language verification."


def _build_subject_review_detail(source_record: SourceBookRecord) -> str:
    subject_source = source_record.field_sources.get("subject")
    if subject_source:
        return f"Subject from {subject_source} did not resolve to an allowed bookstore subject."

    category_source = source_record.field_sources.get("categories")
    if category_source and source_record.categories:
        return f"Categories from {category_source} did not resolve to an allowed bookstore subject."

    return "No source supplied subject or usable categories."


def resolve_book_record(
    source_record: SourceBookRecord,
    subjects_path: Path | None = None,
) -> ResolutionResult:
    reason_codes: list[str] = []
    review_details: list[str] = []
    errors: list[str] = []
    allowed_subject_rows = get_subject_rows(subjects_path) if subjects_path is not None else get_subject_rows()

    resolved_subject = source_record.subject or resolve_subject(source_record.categories, allowed_subject_rows)
    resolved_synopsis = resolve_synopsis(source_record.synopsis, source_record.language)
    synopsis_review_error = get_synopsis_review_error(source_record.synopsis, source_record.language)

    if not source_record.title:
        reason_codes.append(TITLE_MISSING_CODE)
        errors.append(TITLE_MISSING_ERROR)
        review_details.append(_build_missing_field_detail(source_record, "title"))

    if not source_record.author:
        reason_codes.append(AUTHOR_MISSING_CODE)
        errors.append(AUTHOR_MISSING_ERROR)
        review_details.append(_build_missing_field_detail(source_record, "author"))

    if not source_record.editorial:
        reason_codes.append(EDITORIAL_MISSING_CODE)
        errors.append(EDITORIAL_MISSING_ERROR)
        review_details.append(_build_missing_field_detail(source_record, "editorial"))

    if not resolved_synopsis and synopsis_review_error is None:
        reason_codes.append(SYNOPSIS_MISSING_CODE)
        errors.append(SYNOPSIS_MISSING_ERROR)
        review_details.append(_build_missing_field_detail(source_record, "synopsis"))

    if synopsis_review_error:
        reason_codes.append(NON_SPANISH_SYNOPSIS_CODE)
        errors.append(synopsis_review_error)
        review_details.append(_build_synopsis_review_detail(source_record))

    if not resolved_subject:
        reason_codes.append(SUBJECT_MISSING_CODE)
        errors.append(SUBJECT_MISSING_ERROR)
        review_details.append(_build_subject_review_detail(source_record))

    if errors:
        return ResolutionResult(
            record=None,
            source_record=source_record,
            errors=[*errors, *review_details],
            reason_codes=reason_codes,
            review_details=review_details,
        )

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

    return ResolutionResult(
        record=record,
        source_record=source_record,
        errors=[],
        reason_codes=[],
        review_details=[],
    )
