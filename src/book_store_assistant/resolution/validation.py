from difflib import SequenceMatcher

from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.base import RecordQualityValidator
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.models import SourceBookRecord

LLM_VALIDATION_FAILED_CODE = "LLM_VALIDATION_FAILED"
LLM_VALIDATION_FAILED_ERROR = "LLM validation rejected the extracted record."
CRITICAL_VALIDATION_ISSUE_TOKENS = (
    "customer_facing",
    "bibliography",
    "index",
    "reference",
    "navigation",
    "json",
    "fragment",
    "unrelated",
    "unsupported",
    "halluc",
    "fabricat",
    "corrupt",
)


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split()).strip().casefold()


def _synopsis_is_faithful(
    source_record: SourceBookRecord,
    candidate_record: BookRecord,
) -> bool:
    source_synopsis = _normalize_text(source_record.synopsis)
    candidate_synopsis = _normalize_text(candidate_record.synopsis)
    if not source_synopsis or not candidate_synopsis:
        return False
    if source_synopsis == candidate_synopsis:
        return True
    return SequenceMatcher(a=source_synopsis, b=candidate_synopsis).ratio() >= 0.92


def _record_is_faithful_normalization(
    source_record: SourceBookRecord,
    candidate_record: BookRecord,
) -> bool:
    return (
        _normalize_text(source_record.title) == _normalize_text(candidate_record.title)
        and _normalize_text(source_record.author) == _normalize_text(candidate_record.author)
        and _normalize_text(source_record.editorial) == _normalize_text(candidate_record.editorial)
        and _synopsis_is_faithful(source_record, candidate_record)
    )


def _has_critical_validation_issue(issues: list[str], explanation: str | None) -> bool:
    normalized_issue_text = " ".join([*issues, explanation or ""]).casefold()
    return any(token in normalized_issue_text for token in CRITICAL_VALIDATION_ISSUE_TOKENS)


def apply_record_quality_validation(
    resolution_results: list[ResolutionResult],
    validator: RecordQualityValidator | None = None,
) -> list[ResolutionResult]:
    if validator is None:
        return resolution_results

    validated_results: list[ResolutionResult] = []

    for resolution_result in resolution_results:
        if resolution_result.record is None or resolution_result.source_record is None:
            validated_results.append(resolution_result)
            continue

        assessment = validator.validate(
            resolution_result.source_record,
            resolution_result.record,
        )
        if assessment is None:
            validated_results.append(resolution_result)
            continue

        if assessment.accepted:
            validated_results.append(
                resolution_result.model_copy(update={"validation_assessment": assessment})
            )
            continue

        if (
            isinstance(resolution_result.record, BookRecord)
            and not _has_critical_validation_issue(assessment.issues, assessment.explanation)
            and _record_is_faithful_normalization(
                resolution_result.source_record,
                resolution_result.record,
            )
        ):
            validated_results.append(
                resolution_result.model_copy(update={"validation_assessment": assessment})
            )
            continue

        review_details = list(resolution_result.review_details)
        if assessment.explanation:
            review_details.append(assessment.explanation)
        if assessment.issues:
            review_details.append(f"Validation issues: {', '.join(assessment.issues)}")

        validated_results.append(
            resolution_result.model_copy(
                update={
                    "record": None,
                    "validation_assessment": assessment,
                    "errors": [*resolution_result.errors, LLM_VALIDATION_FAILED_ERROR],
                    "reason_codes": [*resolution_result.reason_codes, LLM_VALIDATION_FAILED_CODE],
                    "review_details": review_details,
                }
            )
        )

    return validated_results
