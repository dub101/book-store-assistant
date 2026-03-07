from book_store_assistant.models import BookRecord


def test_book_record_accepts_required_fields() -> None:
    record = BookRecord(
        isbn="9781234567890",
        title="Example Title",
        author="Example Author",
        editorial="Example Editorial",
        synopsis="Resumen en espanol.",
        subject="Narrativa",
    )

    assert record.isbn == "9781234567890"
    assert record.cover_url is None
