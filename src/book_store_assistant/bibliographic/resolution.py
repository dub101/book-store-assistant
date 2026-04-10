import re

from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.resolution.base import RecordQualityValidator
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.resolution.synopsis_resolution import (
    get_synopsis_review_error,
    resolve_synopsis,
)
from book_store_assistant.sources.models import SourceBookRecord

TITLE_MISSING_ERROR = "Title is missing."
AUTHOR_MISSING_ERROR = "Author is missing."
EDITORIAL_MISSING_ERROR = "Editorial is missing."
SYNOPSIS_MISSING_ERROR = "Synopsis is missing."
SUBJECT_MISSING_ERROR = "Subject is missing."
VALIDATION_UNAVAILABLE_ERROR = "LLM validation could not be completed."
VALIDATION_REJECTED_ERROR = "LLM validation rejected the bibliographic record."

TITLE_MISSING_CODE = "MISSING_TITLE"
AUTHOR_MISSING_CODE = "MISSING_AUTHOR"
EDITORIAL_MISSING_CODE = "MISSING_EDITORIAL"
SYNOPSIS_MISSING_CODE = "MISSING_SYNOPSIS"
SUBJECT_MISSING_CODE = "MISSING_SUBJECT"
VALIDATION_UNAVAILABLE_CODE = "VALIDATION_UNAVAILABLE"
VALIDATION_REJECTED_CODE = "VALIDATION_REJECTED"

CATALOG_TITLE_ARTIFACT_PATTERN = re.compile(
    r"\s*\[(?:[^\]]*texto impreso[^\]]*|[^\]]*recurso electr[oó]nico[^\]]*|"
    r"[^\]]*electronic resource[^\]]*)\]\s*",
    re.IGNORECASE,
)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned or None


def _clean_catalog_text(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    normalized = _clean_text(CATALOG_TITLE_ARTIFACT_PATTERN.sub(" ", cleaned))
    return normalized or cleaned


def _clean_title(value: str | None, subtitle: str | None = None) -> str | None:
    cleaned = _clean_catalog_text(value)
    if cleaned is None:
        return None
    cleaned_subtitle = _clean_catalog_text(subtitle)
    if cleaned_subtitle:
        normalized_title = cleaned.casefold()
        for separator in (" : ", ": "):
            suffix = f"{separator}{cleaned_subtitle}"
            if normalized_title.endswith(suffix.casefold()):
                stripped = cleaned[: -len(suffix)].rstrip(" :;-")
                return stripped or cleaned
    return cleaned


def _review_note_from_assessment(
    issues: list[str],
    explanation: str | None,
) -> str:
    if explanation:
        return explanation
    if issues:
        return f"Validation issues: {', '.join(issues)}"
    return "Validation rejected the candidate record."


def _build_candidate_record(source_record: SourceBookRecord) -> BibliographicRecord | None:
    title = _clean_title(source_record.title, source_record.subtitle)
    author = _clean_text(source_record.author)
    editorial = _clean_text(source_record.editorial)

    if not title or not author or not editorial:
        return None

    synopsis = resolve_synopsis(source_record.synopsis, source_record.language)

    try:
        from pydantic import HttpUrl
        cover_url = source_record.cover_url
    except Exception:
        cover_url = None

    return BibliographicRecord(
        isbn=source_record.isbn,
        title=title,
        subtitle=_clean_catalog_text(source_record.subtitle),
        author=author,
        editorial=editorial,
        synopsis=synopsis,
        subject=_clean_text(source_record.subject),
        subject_code=_clean_text(source_record.subject_code),
        cover_url=cover_url,
    )


def resolve_bibliographic_record(
    source_record: SourceBookRecord,
    validator: RecordQualityValidator | None = None,
) -> ResolutionResult:
    reason_codes: list[str] = []
    review_details: list[str] = []
    errors: list[str] = []

    title = _clean_title(source_record.title, source_record.subtitle)
    author = _clean_text(source_record.author)
    editorial = _clean_text(source_record.editorial)
    synopsis = resolve_synopsis(source_record.synopsis, source_record.language)
    synopsis_error = get_synopsis_review_error(source_record.synopsis, source_record.language)
    subject = _clean_text(source_record.subject)

    if not title:
        reason_codes.append(TITLE_MISSING_CODE)
        errors.append(TITLE_MISSING_ERROR)
        review_details.append("No reliable source supplied title.")

    if not author:
        reason_codes.append(AUTHOR_MISSING_CODE)
        errors.append(AUTHOR_MISSING_ERROR)
        review_details.append("No reliable source supplied author.")

    if not editorial:
        reason_codes.append(EDITORIAL_MISSING_CODE)
        errors.append(EDITORIAL_MISSING_ERROR)
        review_details.append("No reliable source supplied editorial.")

    if not synopsis:
        code = SYNOPSIS_MISSING_CODE
        reason_codes.append(code)
        if synopsis_error:
            errors.append(synopsis_error)
            review_details.append(synopsis_error)
        else:
            errors.append(SYNOPSIS_MISSING_ERROR)
            review_details.append("No reliable source supplied a Spanish synopsis.")

    if not subject:
        reason_codes.append(SUBJECT_MISSING_CODE)
        errors.append(SUBJECT_MISSING_ERROR)
        review_details.append("No reliable source supplied subject.")

    candidate_record = _build_candidate_record(source_record)

    if candidate_record is None or reason_codes:
        return ResolutionResult(
            record=None,
            candidate_record=candidate_record,
            source_record=source_record,
            errors=errors,
            reason_codes=reason_codes,
            review_details=review_details,
        )

    if validator is None:
        review_note = "LLM validator is not configured."
        return ResolutionResult(
            record=None,
            candidate_record=candidate_record,
            source_record=source_record,
            errors=[VALIDATION_UNAVAILABLE_ERROR, review_note],
            reason_codes=[VALIDATION_UNAVAILABLE_CODE],
            review_details=[review_note],
        )

    assessment = validator.validate(source_record, candidate_record)
    if assessment is None:
        review_note = "LLM validator returned no decision."
        return ResolutionResult(
            record=None,
            candidate_record=candidate_record,
            source_record=source_record,
            validation_assessment=None,
            errors=[VALIDATION_UNAVAILABLE_ERROR, review_note],
            reason_codes=[VALIDATION_UNAVAILABLE_CODE],
            review_details=[review_note],
        )

    if not assessment.accepted:
        review_note = _review_note_from_assessment(assessment.issues, assessment.explanation)
        return ResolutionResult(
            record=None,
            candidate_record=candidate_record,
            source_record=source_record,
            validation_assessment=assessment,
            errors=[VALIDATION_REJECTED_ERROR, review_note],
            reason_codes=[VALIDATION_REJECTED_CODE],
            review_details=[review_note],
        )

    return ResolutionResult(
        record=candidate_record,
        candidate_record=candidate_record,
        source_record=source_record,
        validation_assessment=assessment,
        errors=[],
        reason_codes=[],
        review_details=[],
    )
