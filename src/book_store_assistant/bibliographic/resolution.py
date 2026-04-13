import re

from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.resolution.base import RecordQualityValidator
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.resolution.synopsis_resolution import resolve_synopsis
from book_store_assistant.sources.models import SourceBookRecord

TITLE_MISSING_ERROR = "Title is missing."
AUTHOR_MISSING_ERROR = "Author is missing."
EDITORIAL_MISSING_ERROR = "Editorial is missing."
VALIDATION_UNAVAILABLE_ERROR = "LLM validation could not be completed."
VALIDATION_REJECTED_ERROR = "LLM validation rejected the bibliographic record."

TITLE_MISSING_CODE = "MISSING_TITLE"
AUTHOR_MISSING_CODE = "MISSING_AUTHOR"
EDITORIAL_MISSING_CODE = "MISSING_EDITORIAL"
VALIDATION_UNAVAILABLE_CODE = "VALIDATION_UNAVAILABLE"
VALIDATION_REJECTED_CODE = "VALIDATION_REJECTED"

CATALOG_TITLE_ARTIFACT_PATTERN = re.compile(
    r"\s*(?:"
    r"\[(?:[^\]]*texto impreso[^\]]*|[^\]]*recurso electr[oó]nico[^\]]*|"
    r"[^\]]*electronic resource[^\]]*)\]"
    r"|"
    r"\((?:[^)]*(?:[Ee]dici[oó]n|[Cc]olecci[oó]n)[^)]*)\)"
    r")\s*",
    re.IGNORECASE,
)

TITLE_ALT_LANGUAGE_PATTERN = re.compile(
    r"\s*[=/]\s*[\(\[]?\s*[A-Z].*$",
)
TITLE_SERIES_PREFIX_PATTERN = re.compile(
    r"^.*?\d+\.\s+",
)

EDITORIAL_CITY_PREFIX_PATTERN = re.compile(
    r"^\s*\[[^\]]*\]\s*,?\s*",
)

_BNE_CITY_NAMES = {
    "madrid", "barcelona", "buenos aires", "méxico", "mexico",
    "bogotá", "bogota", "santiago", "lima", "montevideo",
    "caracas", "quito", "sevilla", "valencia", "bilbao",
    "salamanca", "león", "leon", "málaga", "malaga",
    "pontevedra", "vigo", "girona", "zaragoza", "granada",
    "córdoba", "cordoba", "pamplona", "san sebastián",
    "sant feliu de guíxols",
    "boadilla del monte",
}


def _strip_city_prefix(value: str) -> str:
    result = value
    changed = True
    while changed:
        changed = False
        parts = result.split(",", 1)
        if len(parts) == 2:
            raw_candidate = parts[0].strip().rstrip(";").strip()
            candidate = re.sub(r"\s*\([^)]*\)", "", raw_candidate).strip().lower()
            if candidate in _BNE_CITY_NAMES:
                result = parts[1].strip()
                changed = True
    return result


def _pick_best_editorial_segment(value: str) -> str:
    if ";" not in value:
        return value
    segments = [
        s.strip().strip(",").strip()
        for s in value.split(";")
        if s.strip().strip(",").strip()
    ]
    if not segments:
        return value
    return segments[-1] or value


AUTHOR_INITIAL_PATTERN = re.compile(r"\b([A-ZÁÉÍÓÚÑ])\.\s+(?=[A-ZÁÉÍÓÚÑ]\.)")


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned or None


def _clean_author(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    return AUTHOR_INITIAL_PATTERN.sub(r"\1.", cleaned)


_EDITORIAL_PREFIX_PATTERN = re.compile(
    r"^(?:Editorial|Ediciones|Edición|Edicion)\s+",
    re.IGNORECASE,
)


def _normalize_editorial_name(value: str) -> str:
    result = _EDITORIAL_PREFIX_PATTERN.sub("", value).strip()
    if len(result) < 2:
        return value
    return result or value


def _clean_editorial(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    segmented = _pick_best_editorial_segment(cleaned)
    stripped = EDITORIAL_CITY_PREFIX_PATTERN.sub("", segmented).strip()
    stripped = _strip_city_prefix(stripped) if stripped else segmented
    stripped = _normalize_editorial_name(stripped) if stripped else segmented
    return stripped or cleaned


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
    alt_stripped = TITLE_ALT_LANGUAGE_PATTERN.sub("", cleaned).strip()
    if alt_stripped and len(alt_stripped) >= 3:
        cleaned = alt_stripped
    series_match = TITLE_SERIES_PREFIX_PATTERN.match(cleaned)
    if series_match:
        remainder = cleaned[series_match.end():]
        if remainder and len(remainder) >= 5:
            cleaned = remainder
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
    author = _clean_author(source_record.author)
    editorial = _clean_editorial(source_record.editorial)

    if not title or not author or not editorial:
        return None

    synopsis = resolve_synopsis(source_record.synopsis, source_record.language)

    return BibliographicRecord(
        isbn=source_record.isbn,
        title=title,
        subtitle=_clean_catalog_text(source_record.subtitle),
        author=author,
        editorial=editorial,
        synopsis=synopsis,
        subject=_clean_text(source_record.subject),
        subject_code=_clean_text(source_record.subject_code),
        cover_url=source_record.cover_url,
    )


def resolve_bibliographic_record(
    source_record: SourceBookRecord,
    validator: RecordQualityValidator | None = None,
    skip_validation: bool = False,
) -> ResolutionResult:
    reason_codes: list[str] = []
    review_details: list[str] = []
    errors: list[str] = []

    title = _clean_title(source_record.title, source_record.subtitle)
    author = _clean_author(source_record.author)
    editorial = _clean_editorial(source_record.editorial)

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

    if skip_validation:
        return ResolutionResult(
            record=candidate_record,
            candidate_record=candidate_record,
            source_record=source_record,
            errors=[],
            reason_codes=[],
            review_details=[],
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
