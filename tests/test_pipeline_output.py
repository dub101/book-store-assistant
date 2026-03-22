from book_store_assistant.bibliographic.models import BibliographicRecord
from book_store_assistant.pipeline.output import collect_resolved_records
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.models import SourceBookRecord


def test_collect_resolved_records_returns_only_present_records() -> None:
    source_record = SourceBookRecord(source_name="google_books", isbn="9780306406157")

    results = [
        ResolutionResult(
            record=None,
            source_record=source_record,
            errors=["Synopsis is missing."],
        ),
        ResolutionResult(
            record=BibliographicRecord(
                isbn="0306406152",
                title="Example Title",
                author="Example Author",
                editorial="Example Editorial",
                publisher="Example Publisher",
            ),
            source_record=source_record,
            errors=[],
        ),
    ]

    records = collect_resolved_records(results)

    assert len(records) == 1
    assert records[0].isbn == "0306406152"
