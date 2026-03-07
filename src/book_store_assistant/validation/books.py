from book_store_assistant.models import BookRecord


def validate_book_record(record: BookRecord) -> list[str]:
    """Return validation errors for a book record."""
    errors: list[str] = []

    if not record.isbn.strip():
        errors.append("ISBN is required.")
    if not record.title.strip():
        errors.append("Title is required.")
    if not record.author.strip():
        errors.append("Author is required.")
    if not record.editorial.strip():
        errors.append("Editorial is required.")
    if not record.synopsis.strip():
        errors.append("Synopsis is required.")
    if not record.subject.strip():
        errors.append("Subject is required.")

    return errors
