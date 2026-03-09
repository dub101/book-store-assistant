from book_store_assistant.sources.models import SourceBookRecord


def test_source_book_record_allows_partial_metadata() -> None:
    record = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        title="Example Title",
    )

    assert record.source_name == "google_books"
    assert record.title == "Example Title"
    assert record.author is None
    assert record.field_sources == {}
