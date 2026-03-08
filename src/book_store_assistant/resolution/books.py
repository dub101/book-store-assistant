from book_store_assistant.models import BookRecord
from book_store_assistant.sources.models import SourceBookRecord


def resolve_book_record(source_record: SourceBookRecord) -> BookRecord | None:
    if not all(
        [
            source_record.title,
            source_record.author,
            source_record.editorial,
            source_record.synopsis,
            source_record.subject,
        ]
    ):
        return None

    return BookRecord(
        isbn=source_record.isbn,
        title=source_record.title,
        subtitle=source_record.subtitle,
        author=source_record.author,
        editorial=source_record.editorial,
        synopsis=source_record.synopsis,
        subject=source_record.subject,
        cover_url=source_record.cover_url,
    )
