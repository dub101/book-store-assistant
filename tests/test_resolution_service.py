from book_store_assistant.bibliographic.models import BibliographicRecord
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
                synopsis="Sinopsis de ejemplo.",
                subject="NOVELA",
                subject_code="20",
                language="es",
            ),
            errors=[],
        ),
    ]

    results = resolve_all(fetch_results, validator=AcceptingValidator())

    assert results[0].record is None
    assert results[0].source_record is not None
    assert results[0].source_record.source_name == "fetch_error"
    assert isinstance(results[1].record, BibliographicRecord)
    assert results[1].record.editorial == "Example Editorial"
    assert results[1].record.synopsis == "Sinopsis de ejemplo."
    assert results[1].record.subject == "NOVELA"
    assert results[1].record.subject_code == "20"


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
                synopsis="Sinopsis de ejemplo.",
                subject="NOVELA",
                subject_code="20",
                language="es",
            ),
            errors=[],
        ),
    ]

    results = resolve_all(fetch_results, validator=RejectingValidator())

    assert results[0].record is None
    assert results[0].candidate_record is not None
    assert results[0].reason_codes == ["VALIDATION_REJECTED"]
    assert results[0].validation_assessment is not None


def test_resolve_all_strips_catalog_suffixes_from_titles() -> None:
    fetch_results = [
        FetchResult(
            isbn="9788449326134",
            record=SourceBookRecord(
                source_name="bne",
                isbn="9788449326134",
                title="Psicologia y simbolica del arquetipo [Texto impreso] : ensayo",
                subtitle="ensayo",
                author="Carl Gustav Jung",
                editorial="Paidos",
                synopsis="Sinopsis del libro en español.",
                subject="ENSAYO",
                subject_code="30",
                language="es",
            ),
            errors=[],
        ),
    ]

    results = resolve_all(fetch_results, validator=AcceptingValidator())

    assert results[0].record is not None
    assert results[0].record.title == "Psicologia y simbolica del arquetipo"
    assert results[0].record.subtitle == "ensayo"


def test_resolve_all_flags_missing_synopsis_as_incomplete() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Example Title",
                author="Example Author",
                editorial="Example Editorial",
            ),
            errors=[],
        ),
    ]

    results = resolve_all(fetch_results, validator=AcceptingValidator())

    assert results[0].record is None
    assert "MISSING_SYNOPSIS" in results[0].reason_codes


def test_resolve_all_flags_missing_subject_as_incomplete() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Example Title",
                author="Example Author",
                editorial="Example Editorial",
                synopsis="Sinopsis de ejemplo.",
                language="es",
            ),
            errors=[],
        ),
    ]

    results = resolve_all(fetch_results, validator=AcceptingValidator())

    assert results[0].record is None
    assert "MISSING_SUBJECT" in results[0].reason_codes
