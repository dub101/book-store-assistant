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


def test_resolve_all_resolves_record_without_synopsis() -> None:
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

    assert results[0].record is not None
    assert results[0].record.title == "Example Title"


def test_resolve_all_resolves_record_without_subject() -> None:
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

    assert results[0].record is not None
    assert results[0].record.title == "Example Title"
    assert results[0].record.synopsis == "Sinopsis de ejemplo."


def test_resolve_all_fetch_result_record_none_creates_fetch_error_record() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=None,
            errors=["Connection timed out."],
            issue_codes=["GOOGLE_BOOKS_TIMEOUT"],
        ),
    ]

    results = resolve_all(fetch_results)

    assert len(results) == 1
    result = results[0]
    assert result.record is None
    assert result.source_record is not None
    assert result.source_record.source_name == "fetch_error"
    assert result.source_record.isbn == "9780306406157"
    assert "FETCH_ERROR" in result.reason_codes
    assert "Connection timed out." in result.errors
    assert any("GOOGLE_BOOKS_TIMEOUT" in d for d in result.review_details)


def test_resolve_all_preserves_diagnostics_in_output() -> None:
    diag = [{"stage": "google_books", "action": "started"}]
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
            errors=[],
            diagnostics=diag,
        ),
    ]

    results = resolve_all(fetch_results, validator=AcceptingValidator())

    assert results[0].diagnostics == diag
    assert results[0].path_summary["stages_seen"] == ["google_books"]


def test_resolve_all_with_fetch_errors_and_resolution_errors_merges_both() -> None:
    """When record exists but resolution fails AND fetch had errors, both merge."""
    fetch_results = [
        FetchResult(
            isbn="0306406152",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="0306406152",
                title="Example Title",
                author=None,
                editorial="Example Editorial",
            ),
            errors=["Partial data returned."],
            issue_codes=["GOOGLE_BOOKS_PARTIAL"],
        ),
    ]

    results = resolve_all(fetch_results)

    result = results[0]
    assert result.record is None
    assert "FETCH_ERROR" in result.reason_codes
    assert "MISSING_AUTHOR" in result.reason_codes
    assert "Partial data returned." in result.errors
    assert any("GOOGLE_BOOKS_PARTIAL" in d for d in result.review_details)


class TrackingValidator:
    """Validator that tracks calls and accepts everything."""

    def __init__(self):
        self.calls = []

    def validate(self, source_record, candidate_record):
        self.calls.append(source_record.isbn)
        return RecordValidationAssessment(accepted=True, confidence=0.95)


def test_resolve_all_skips_validation_for_high_confidence_single_source() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="isbndb",
                isbn="9780306406157",
                title="ISBNdb Title",
                author="ISBNdb Author",
                editorial="ISBNdb Editorial",
                field_sources={
                    "title": "isbndb",
                    "author": "isbndb",
                    "editorial": "isbndb",
                },
                field_confidence={
                    "title": 0.9,
                    "author": 0.9,
                    "editorial": 0.9,
                },
            ),
            errors=[],
        ),
    ]

    tracker = TrackingValidator()
    results = resolve_all(fetch_results, validator=tracker)

    assert results[0].record is not None
    assert tracker.calls == []


def test_resolve_all_validates_when_llm_contributed() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="isbndb + llm_web_search",
                isbn="9780306406157",
                title="ISBNdb Title",
                author="ISBNdb Author",
                editorial="LLM Editorial",
                field_sources={
                    "title": "isbndb",
                    "author": "isbndb",
                    "editorial": "llm_web_search",
                },
                field_confidence={
                    "title": 0.9,
                    "author": 0.9,
                    "editorial": 0.85,
                },
            ),
            errors=[],
        ),
    ]

    tracker = TrackingValidator()
    results = resolve_all(fetch_results, validator=tracker)

    assert results[0].record is not None
    assert tracker.calls == ["9780306406157"]


def test_resolve_all_validates_when_low_confidence() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="open_library",
                isbn="9780306406157",
                title="OL Title",
                author="OL Author",
                editorial="OL Editorial",
                field_sources={
                    "title": "open_library",
                    "author": "open_library",
                    "editorial": "open_library",
                },
                field_confidence={
                    "title": 0.6,
                    "author": 0.6,
                    "editorial": 0.6,
                },
            ),
            errors=[],
        ),
    ]

    tracker = TrackingValidator()
    results = resolve_all(fetch_results, validator=tracker)

    assert results[0].record is not None
    assert tracker.calls == ["9780306406157"]


def test_resolve_all_validates_when_multiple_sources_disagree() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="isbndb + bne",
                isbn="9780306406157",
                title="ISBNdb Title",
                author="BNE Author",
                editorial="ISBNdb Editorial",
                field_sources={
                    "title": "isbndb",
                    "author": "bne",
                    "editorial": "isbndb",
                },
                field_confidence={
                    "title": 0.9,
                    "author": 1.0,
                    "editorial": 0.9,
                },
            ),
            errors=[],
        ),
    ]

    tracker = TrackingValidator()
    results = resolve_all(fetch_results, validator=tracker)

    assert results[0].record is not None
    assert tracker.calls == ["9780306406157"]
