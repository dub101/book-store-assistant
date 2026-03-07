from book_store_assistant.models import BookRecord
from book_store_assistant.validation.books import validate_book_record


def test_validate_book_record_returns_error_for_missing_required_fields() -> None:
    record = BookRecord(
        isbn="9781234567890",
        title="Example Title",
        author="Example Author",
        editorial="Example Editorial",
        synopsis="Resumen",
        subject="Narrativa",
    )

    errors = validate_book_record(record.model_copy(update={"title": "  ", "subject": ""}))

    assert "Title is required." in errors
    assert "Subject is required." in errors
