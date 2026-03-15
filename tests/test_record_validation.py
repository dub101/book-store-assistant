from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.models import RecordValidationAssessment
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.resolution.validation import (
    LLM_VALIDATION_FAILED_CODE,
    apply_record_quality_validation,
)
from book_store_assistant.sources.models import SourceBookRecord


class StubRecordValidator:
    def __init__(self, accepted: bool, confidence: float = 0.95) -> None:
        self.accepted = accepted
        self.confidence = confidence
        self.calls = 0

    def validate(
        self,
        source_record: SourceBookRecord,
        candidate_record: BookRecord,
    ) -> RecordValidationAssessment | None:
        self.calls += 1
        return RecordValidationAssessment(
            accepted=self.accepted,
            confidence=self.confidence,
            issues=["synopsis_not_customer_facing"] if not self.accepted else [],
            explanation="Synopsis is bibliography-only." if not self.accepted else None,
        )


def test_apply_record_quality_validation_keeps_accepted_record() -> None:
    validator = StubRecordValidator(accepted=True)
    source_record = SourceBookRecord(
        source_name="bne",
        isbn="9780306406157",
        title="Example Title",
        author="Example Author",
        editorial="Example Editorial",
        synopsis="Resumen del libro.",
        language="es",
    )
    resolution_results = [
        ResolutionResult(
            record=BookRecord(
                isbn="9780306406157",
                title="Example Title",
                author="Example Author",
                editorial="Example Editorial",
                synopsis="Resumen del libro.",
                subject="FICCION",
            ),
            source_record=source_record,
            errors=[],
        )
    ]

    validated = apply_record_quality_validation(resolution_results, validator=validator)

    assert validated[0].record is not None
    assert validated[0].validation_assessment is not None
    assert validator.calls == 1


def test_apply_record_quality_validation_rejects_record() -> None:
    validator = StubRecordValidator(accepted=False)
    source_record = SourceBookRecord(
        source_name="bne",
        isbn="9780306406157",
        title="Poesia",
        author="Luis de Leon",
        editorial="Galaxia Gutenberg",
        synopsis="Bibliografía: p. 777-826. Índices",
        language="es",
    )
    resolution_results = [
        ResolutionResult(
            record=BookRecord(
                isbn="9780306406157",
                title="Poesia",
                author="Luis de Leon",
                editorial="Galaxia Gutenberg",
                synopsis="Bibliografía: p. 777-826. Índices",
                subject="POESÍA",
            ),
            source_record=source_record,
            errors=[],
        )
    ]

    validated = apply_record_quality_validation(resolution_results, validator=validator)

    assert validated[0].record is None
    assert LLM_VALIDATION_FAILED_CODE in validated[0].reason_codes
    assert "Synopsis is bibliography-only." in validated[0].review_details
    assert "Validation issues: synopsis_not_customer_facing" in validated[0].review_details
