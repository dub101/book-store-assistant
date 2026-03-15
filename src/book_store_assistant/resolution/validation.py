from book_store_assistant.resolution.base import RecordQualityValidator
from book_store_assistant.resolution.results import ResolutionResult

LLM_VALIDATION_FAILED_CODE = "LLM_VALIDATION_FAILED"
LLM_VALIDATION_FAILED_ERROR = "LLM validation rejected the extracted record."


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
