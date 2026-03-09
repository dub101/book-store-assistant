import pytest

from book_store_assistant.sources.merge import merge_source_records
from book_store_assistant.sources.models import SourceBookRecord


def test_merge_source_records_requires_at_least_one_record() -> None:
    with pytest.raises(ValueError, match="at least one record"):
        merge_source_records([])


def test_merge_source_records_fills_missing_fields_from_later_records() -> None:
    merged = merge_source_records(
        [
            SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Example Title",
                author="Primary Author",
                categories=["Fiction"],
            ),
            SourceBookRecord(
                source_name="open_library",
                isbn="9780306406157",
                editorial="Later Editorial",
                synopsis="Sinopsis en espanol.",
                subject="Novela",
                categories=["fiction", "Drama"],
                language="es",
            ),
        ]
    )

    assert merged.source_name == "google_books + open_library"
    assert merged.title == "Example Title"
    assert merged.author == "Primary Author"
    assert merged.editorial == "Later Editorial"
    assert merged.synopsis == "Sinopsis en espanol."
    assert merged.subject == "Novela"
    assert merged.language == "es"
    assert merged.categories == ["Fiction", "Drama"]


def test_merge_source_records_does_not_override_existing_values() -> None:
    merged = merge_source_records(
        [
            SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Primary Title",
                author="Primary Author",
                editorial="Primary Editorial",
                synopsis="Sinopsis primaria.",
                subject="Historia",
                language="es",
            ),
            SourceBookRecord(
                source_name="open_library",
                isbn="9780306406157",
                title="Secondary Title",
                author="Secondary Author",
                editorial="Secondary Editorial",
                synopsis="Sinopsis secundaria.",
                subject="Novela",
                language="en",
            ),
        ]
    )

    assert merged.title == "Primary Title"
    assert merged.author == "Primary Author"
    assert merged.editorial == "Primary Editorial"
    assert merged.synopsis == "Sinopsis primaria."
    assert merged.subject == "Historia"
    assert merged.language == "es"


def test_merge_source_records_deduplicates_source_names_and_categories() -> None:
    merged = merge_source_records(
        [
            SourceBookRecord(
                source_name="google_books + open_library",
                isbn="9780306406157",
                categories=["Fiction", "Drama"],
            ),
            SourceBookRecord(
                source_name="open_library",
                isbn="9780306406157",
                categories=["fiction", "Poetry"],
            ),
        ]
    )

    assert merged.source_name == "google_books + open_library"
    assert merged.categories == ["Fiction", "Drama", "Poetry"]
