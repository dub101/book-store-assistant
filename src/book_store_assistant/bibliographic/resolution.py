import re

from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.publisher_identity.models import PublisherIdentityResult
from book_store_assistant.resolution.base import RecordQualityValidator
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.models import SourceBookRecord

TITLE_MISSING_ERROR = "Title is missing."
AUTHOR_MISSING_ERROR = "Author is missing."
EDITORIAL_MISSING_ERROR = "Editorial is missing."
PUBLISHER_MISSING_ERROR = "Publisher is missing."
VALIDATION_UNAVAILABLE_ERROR = "LLM validation could not be completed."
VALIDATION_REJECTED_ERROR = "LLM validation rejected the bibliographic record."

TITLE_MISSING_CODE = "MISSING_TITLE"
AUTHOR_MISSING_CODE = "MISSING_AUTHOR"
EDITORIAL_MISSING_CODE = "MISSING_EDITORIAL"
PUBLISHER_MISSING_CODE = "MISSING_PUBLISHER"
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


def _coalesce_editorial_and_publisher(
    source_record: SourceBookRecord,
    publisher_identity: PublisherIdentityResult | None,
) -> tuple[str | None, str | None]:
    editorial = (
        _clean_text(publisher_identity.imprint_name if publisher_identity is not None else None)
        or _clean_text(source_record.editorial)
        or _clean_text(
            publisher_identity.publisher_name if publisher_identity is not None else None
        )
    )
    publisher = (
        _clean_text(
            publisher_identity.publisher_name if publisher_identity is not None else None
        )
        or editorial
    )

    if editorial is None and publisher is not None:
        editorial = publisher
    if publisher is None and editorial is not None:
        publisher = editorial

    return editorial, publisher


def _build_candidate_record(
    source_record: SourceBookRecord,
    publisher_identity: PublisherIdentityResult | None,
) -> BibliographicRecord | None:
    title = _clean_title(source_record.title, source_record.subtitle)
    author = _clean_text(source_record.author)
    editorial, publisher = _coalesce_editorial_and_publisher(
        source_record,
        publisher_identity,
    )

    if not title or not author or not editorial or not publisher:
        return None

    return BibliographicRecord(
        isbn=source_record.isbn,
        title=title,
        subtitle=_clean_catalog_text(source_record.subtitle),
        author=author,
        editorial=editorial,
        publisher=publisher,
    )


def resolve_bibliographic_record(
    source_record: SourceBookRecord,
    publisher_identity: PublisherIdentityResult | None = None,
    validator: RecordQualityValidator | None = None,
) -> ResolutionResult:
    reason_codes: list[str] = []
    review_details: list[str] = []
    errors: list[str] = []
    candidate_record = _build_candidate_record(source_record, publisher_identity)
    editorial, publisher = _coalesce_editorial_and_publisher(source_record, publisher_identity)

    if not _clean_title(source_record.title, source_record.subtitle):
        reason_codes.append(TITLE_MISSING_CODE)
        errors.append(TITLE_MISSING_ERROR)
        review_details.append("No reliable source supplied title.")

    if not _clean_text(source_record.author):
        reason_codes.append(AUTHOR_MISSING_CODE)
        errors.append(AUTHOR_MISSING_ERROR)
        review_details.append("No reliable source supplied author.")

    if not editorial:
        reason_codes.append(EDITORIAL_MISSING_CODE)
        errors.append(EDITORIAL_MISSING_ERROR)
        review_details.append("No reliable source supplied editorial.")

    if not publisher:
        reason_codes.append(PUBLISHER_MISSING_CODE)
        errors.append(PUBLISHER_MISSING_ERROR)
        review_details.append("No reliable source supplied publisher.")

    if candidate_record is None:
        return ResolutionResult(
            record=None,
            candidate_record=None,
            source_record=source_record,
            publisher_identity=publisher_identity,
            errors=[*errors, *review_details],
            reason_codes=reason_codes,
            review_details=review_details,
        )

    if validator is None:
        review_note = "LLM validator is not configured."
        return ResolutionResult(
            record=None,
            candidate_record=candidate_record,
            source_record=source_record,
            publisher_identity=publisher_identity,
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
            publisher_identity=publisher_identity,
            validation_assessment=None,
            errors=[VALIDATION_UNAVAILABLE_ERROR, review_note],
            reason_codes=[VALIDATION_UNAVAILABLE_CODE],
            review_details=[review_note],
        )

    if not assessment.accepted:
        review_note = _review_note_from_assessment(
            assessment.issues,
            assessment.explanation,
        )
        return ResolutionResult(
            record=None,
            candidate_record=candidate_record,
            source_record=source_record,
            publisher_identity=publisher_identity,
            validation_assessment=assessment,
            errors=[VALIDATION_REJECTED_ERROR, review_note],
            reason_codes=[VALIDATION_REJECTED_CODE],
            review_details=[review_note],
        )

    return ResolutionResult(
        record=candidate_record,
        candidate_record=candidate_record,
        source_record=source_record,
        publisher_identity=publisher_identity,
        validation_assessment=assessment,
        errors=[],
        reason_codes=[],
        review_details=[],
    )
