from pathlib import Path

from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.base import RecordFieldSelector, SubjectMapper
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.resolution.subject_resolution import resolve_subject
from book_store_assistant.resolution.synopsis_resolution import (
    get_synopsis_review_error,
    resolve_synopsis,
)
from book_store_assistant.sources.candidates import get_field_candidates
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.subject_mapping import (
    find_subject_entry_by_description,
    get_subject_entries,
    get_subject_rows,
)

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


def _build_subject_review_detail(
    source_record: SourceBookRecord,
    resolved_subject: str | None,
) -> str:
    subject_source = source_record.field_sources.get("subject")
    if subject_source:
        return f"Subject from {subject_source} did not resolve to an allowed bookstore subject."

    if source_record.subject:
        return f"Subject '{source_record.subject}' did not resolve to an allowed bookstore subject."

    category_source = source_record.field_sources.get("categories")
    if category_source and source_record.categories:
        return f"Categories from {category_source} did not resolve to an allowed bookstore subject."

    if resolved_subject:
        return f"Subject '{resolved_subject}' did not resolve to an allowed bookstore subject."

    return "No source supplied subject or usable categories."


def _add_issue(
    reason_codes: list[str],
    errors: list[str],
    review_details: list[str],
    reason_code: str,
    error: str,
    detail: str,
) -> None:
    reason_codes.append(reason_code)
    errors.append(error)
    review_details.append(detail)


def _resolve_catalog_subject(
    source_record: SourceBookRecord,
    allowed_subject_rows: list[list[str]],
) -> str | None:
    if source_record.subject:
        resolved_direct_subject = resolve_subject(
            [source_record.subject],
            allowed_subject_rows,
        )
        if resolved_direct_subject is not None:
            return resolved_direct_subject

    return resolve_subject(source_record.categories, allowed_subject_rows)


def _apply_selected_field(
    record: SourceBookRecord,
    field_name: str,
    selected_value: str | None,
) -> SourceBookRecord:
    if not selected_value:
        return record

    candidate = next(
        (
            item
            for item in get_field_candidates(record, field_name)
            if item.value == selected_value
        ),
        None,
    )
    if candidate is None:
        return record.model_copy(update={field_name: selected_value})

    field_sources = dict(record.field_sources)
    field_confidence = dict(record.field_confidence)
    field_sources[field_name] = candidate.source_name
    field_confidence[field_name] = candidate.confidence

    return record.model_copy(
        update={
            field_name: candidate.value,
            "field_sources": field_sources,
            "field_confidence": field_confidence,
        }
    )


def _select_record_fields(
    source_record: SourceBookRecord,
    record_selector: RecordFieldSelector | None,
) -> SourceBookRecord:
    if record_selector is None:
        return source_record

    selection = record_selector.select_fields(source_record)
    if selection is None:
        return source_record

    selected_record = _apply_selected_field(source_record, "title", selection.title)
    selected_record = _apply_selected_field(selected_record, "author", selection.author)
    selected_record = _apply_selected_field(selected_record, "editorial", selection.editorial)
    return selected_record


def resolve_book_record(
    source_record: SourceBookRecord,
    subjects_path: Path | None = None,
    subject_mapper: SubjectMapper | None = None,
    record_selector: RecordFieldSelector | None = None,
) -> ResolutionResult:
    effective_record = _select_record_fields(source_record, record_selector)
    reason_codes: list[str] = []
    review_details: list[str] = []
    errors: list[str] = []
    allowed_subject_rows = (
        get_subject_rows(subjects_path) if subjects_path is not None else get_subject_rows()
    )
    allowed_subject_entries = (
        get_subject_entries(subjects_path) if subjects_path is not None else get_subject_entries()
    )

    resolved_subject = _resolve_catalog_subject(effective_record, allowed_subject_rows)
    if resolved_subject is None and subject_mapper is not None:
        resolved_subject = subject_mapper.map_subject(effective_record, allowed_subject_entries)
    subject_entry = (
        find_subject_entry_by_description(resolved_subject, path=subjects_path)
        if resolved_subject is not None and subjects_path is not None
        else find_subject_entry_by_description(resolved_subject)
        if resolved_subject is not None
        else None
    )
    resolved_synopsis = resolve_synopsis(effective_record.synopsis, effective_record.language)
    synopsis_review_error = get_synopsis_review_error(
        effective_record.synopsis,
        effective_record.language,
    )

    if not effective_record.title:
        _add_issue(
            reason_codes,
            errors,
            review_details,
            TITLE_MISSING_CODE,
            TITLE_MISSING_ERROR,
            _build_missing_field_detail(effective_record, "title"),
        )

    if not effective_record.author:
        _add_issue(
            reason_codes,
            errors,
            review_details,
            AUTHOR_MISSING_CODE,
            AUTHOR_MISSING_ERROR,
            _build_missing_field_detail(effective_record, "author"),
        )

    if not effective_record.editorial:
        _add_issue(
            reason_codes,
            errors,
            review_details,
            EDITORIAL_MISSING_CODE,
            EDITORIAL_MISSING_ERROR,
            _build_missing_field_detail(effective_record, "editorial"),
        )

    if not resolved_synopsis and synopsis_review_error is None:
        _add_issue(
            reason_codes,
            errors,
            review_details,
            SYNOPSIS_MISSING_CODE,
            SYNOPSIS_MISSING_ERROR,
            _build_missing_field_detail(effective_record, "synopsis"),
        )

    if synopsis_review_error:
        _add_issue(
            reason_codes,
            errors,
            review_details,
            NON_SPANISH_SYNOPSIS_CODE,
            synopsis_review_error,
            _build_synopsis_review_detail(effective_record),
        )

    if subject_entry is None:
        _add_issue(
            reason_codes,
            errors,
            review_details,
            SUBJECT_MISSING_CODE,
            SUBJECT_MISSING_ERROR,
            _build_subject_review_detail(effective_record, resolved_subject),
        )

    if errors:
        return ResolutionResult(
            record=None,
            source_record=effective_record,
            errors=[*errors, *review_details],
            reason_codes=reason_codes,
            review_details=review_details,
        )

    assert effective_record.title is not None
    assert effective_record.author is not None
    assert effective_record.editorial is not None
    assert resolved_synopsis is not None
    assert resolved_subject is not None

    record = BookRecord(
        isbn=effective_record.isbn,
        title=effective_record.title,
        subtitle=effective_record.subtitle,
        author=effective_record.author,
        editorial=effective_record.editorial,
        synopsis=resolved_synopsis,
        subject=resolved_subject,
        cover_url=effective_record.cover_url,
    )

    return ResolutionResult(
        record=record,
        source_record=effective_record,
        errors=[],
        reason_codes=[],
        review_details=[],
    )
