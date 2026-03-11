from pathlib import Path

from book_store_assistant.sources.intermediate import export_fetch_results, read_fetch_results
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


def test_fetch_results_can_roundtrip_through_intermediate_excel(tmp_path: Path) -> None:
    output_file = tmp_path / "cache.xlsx"
    results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                source_url="https://example.com/book",
                title="Example Title",
                subtitle="Example Subtitle",
                author="Example Author",
                editorial="Example Editorial",
                synopsis="Resumen del libro.",
                subject="FICCION",
                categories=["Fiction", "Drama"],
                cover_url="https://example.com/cover.jpg",
                language="es",
                field_sources={"title": "google_books", "categories": "google_books"},
            ),
            errors=["google_books: Timeout"],
            issue_codes=["GOOGLE_BOOKS:GOOGLE_BOOKS_TIMEOUT"],
        ),
        FetchResult(
            isbn="9780306406158",
            record=None,
            errors=[],
            issue_codes=[],
        ),
    ]

    export_fetch_results(results, output_file)
    loaded = read_fetch_results(output_file)

    assert loaded == results
