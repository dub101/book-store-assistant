from book_store_assistant.models import BookRecord
from book_store_assistant.resolution.results import ResolutionResult
from book_store_assistant.sources.models import SourceBookRecord


def resolve_book_record(source_record: SourceBookRecord) -> ResolutionResult:
    errors: list[str] = []

    if not source_record.title:
        errors.append("Title is missing.")
    if not source_record.author:
        errors.append("Author is missing.")
    if not source_record.editorial:
        errors.append("Editorial is missing.")
    if not source_record.synopsis:
        errors.append("Synopsis is missing.")
    if not source_record.subject:
        errors.append("Subject is missing.")

    if errors:
        return ResolutionResult(record=None, source_record=source_record, errors=errors)

    record = BookRecord(
        isbn=source_record.isbn,
        title=source_record.title,
        subtitle=source_record.subtitle,
        author=source_record.author,
        editorial=source_record.editorial,
        synopsis=source_record.synopsis,
        subject=source_record.subject,
        cover_url=source_record.cover_url,
    )

    return ResolutionResult(record=record, source_record=source_record, errors=[])
