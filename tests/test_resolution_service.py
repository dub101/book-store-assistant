from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.publisher_identity.models import PublisherIdentityResult
from book_store_assistant.resolution.models import RecordValidationAssessment
from book_store_assistant.resolution.service import resolve_all
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


class AcceptingValidator:
    def validate(self, source_record, candidate_record):
        return RecordValidationAssessment(accepted=True, confidence=0.98)


class RejectingValidator:
    def validate(self, source_record, candidate_record):
        return RecordValidationAssessment(
            accepted=False,
            confidence=0.41,
            issues=["author_mismatch"],
            explanation="Author is not well supported by the source evidence.",
        )


def test_resolve_all_handles_fetch_errors_and_resolved_bibliographic_records() -> None:
    fetch_results = [
        FetchResult(isbn="9780306406157", record=None, errors=["No Google Books match found."]),
        FetchResult(
            isbn="0306406152",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="0306406152",
                title="Example Title",
                subtitle="Example Subtitle",
                author="Example Author",
                editorial="Example Editorial",
            ),
            publisher_identity=PublisherIdentityResult(
                isbn="0306406152",
                publisher_name="Example Publisher",
                imprint_name="Example Editorial",
            ),
            errors=[],
        ),
    ]

    results = resolve_all(fetch_results, validator=AcceptingValidator())

    assert results[0].record is None
    assert results[0].source_record is not None
    assert results[0].source_record.source_name == "fetch_error"
    assert isinstance(results[1].record, BibliographicRecord)
    assert results[1].record.publisher == "Example Publisher"


def test_resolve_all_routes_rejected_candidates_to_review() -> None:
    fetch_results = [
        FetchResult(
            isbn="0306406152",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="0306406152",
                title="Example Title",
                author="Example Author",
                editorial="Example Editorial",
            ),
            publisher_identity=PublisherIdentityResult(
                isbn="0306406152",
                publisher_name="Example Publisher",
                imprint_name="Example Editorial",
            ),
            errors=[],
        ),
    ]

    results = resolve_all(fetch_results, validator=RejectingValidator())

    assert results[0].record is None
    assert results[0].candidate_record is not None
    assert results[0].reason_codes == ["VALIDATION_REJECTED"]
    assert results[0].validation_assessment is not None
