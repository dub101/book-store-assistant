from book_store_assistant.models import BookRecord
from book_store_assistant.pipeline.review import collect_unresolved_results
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.models import SourceBookRecord


def test_collect_unresolved_results_returns_only_missing_records() -> None:
    source_record = SourceBookRecord(source_name="google_books", isbn="9780306406157")

    results = [
        ResolutionResult(
            record=None,
            source_record=source_record,
            errors=["Synopsis is missing."],
        ),
        ResolutionResult(
            record=BookRecord(
                isbn="0306406152",
                title="Example Title",
                author="Example Author",
                editorial="Example Editorial",
                synopsis="Resumen del libro.",
                subject="Narrativa",
            ),
            source_record=source_record,
            errors=[],
        ),
    ]

    unresolved = collect_unresolved_results(results)

    assert len(unresolved) == 1
    assert unresolved[0].errors == ["Synopsis is missing."]
