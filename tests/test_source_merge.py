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
                source_url="https://example.com/google",
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
    assert str(merged.source_url) == "https://example.com/google"
    assert merged.title == "Example Title"
    assert merged.author == "Primary Author"
    assert merged.editorial == "Later Editorial"
    assert merged.synopsis == "Sinopsis en espanol."
    assert merged.subject == "Novela"
    assert merged.language == "es"
    assert merged.categories == ["Fiction", "Drama"]
    assert merged.field_sources == {
        "title": "google_books",
        "author": "google_books",
        "source_url": "google_books",
        "editorial": "open_library",
        "synopsis": "open_library",
        "subject": "open_library",
        "language": "open_library",
        "categories": "google_books + open_library",
    }
    assert merged.field_confidence == {
        "title": 0.75,
        "author": 0.75,
        "source_url": 0.75,
        "editorial": 0.6,
        "synopsis": 0.6,
        "subject": 0.6,
        "language": 0.6,
        "categories": 0.75,
    }


def test_merge_source_records_does_not_override_existing_values() -> None:
    merged = merge_source_records(
        [
            SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                source_url="https://example.com/google",
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
                source_url="https://example.com/open-library",
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
    assert str(merged.source_url) == "https://example.com/google"
    assert merged.author == "Primary Author"
    assert merged.editorial == "Primary Editorial"
    assert merged.synopsis == "Sinopsis primaria."
    assert merged.subject == "Historia"
    assert merged.language == "es"
    assert merged.field_sources == {
        "title": "google_books",
        "source_url": "google_books",
        "author": "google_books",
        "editorial": "google_books",
        "synopsis": "google_books",
        "subject": "google_books",
        "language": "google_books",
    }
    assert merged.field_confidence == {
        "title": 0.75,
        "source_url": 0.75,
        "author": 0.75,
        "editorial": 0.75,
        "synopsis": 0.75,
        "subject": 0.75,
        "language": 0.75,
    }


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
    assert merged.field_sources == {
        "categories": "google_books + open_library",
    }
    assert merged.field_confidence == {
        "categories": 0.75,
    }


def test_merge_source_records_prefers_higher_confidence_values() -> None:
    merged = merge_source_records(
        [
            SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Generic Title",
                editorial="Generic Editorial",
            ),
            SourceBookRecord(
                source_name="bne",
                isbn="9780306406157",
                title="Authoritative Title",
                editorial="Authoritative Editorial",
            ),
        ]
    )

    assert merged.title == "Authoritative Title"
    assert merged.editorial == "Authoritative Editorial"
    assert merged.field_sources["title"] == "bne"
    assert merged.field_sources["editorial"] == "bne"
    assert merged.field_confidence["title"] == 1.0
    assert merged.field_confidence["editorial"] == 1.0
