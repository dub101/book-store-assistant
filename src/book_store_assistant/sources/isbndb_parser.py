from book_store_assistant.sources.language_codes import normalize_language_code
from book_store_assistant.sources.models import SourceBookRecord


def _extract_subtitle(title: str | None, title_long: str | None) -> str | None:
    if not title_long or not title:
        return None

    if title_long == title:
        return None

    if ": " in title_long:
        _, _, subtitle = title_long.partition(": ")
        subtitle = subtitle.strip()
        if subtitle:
            return subtitle

    return None


def parse_isbndb_payload(payload: dict, isbn: str) -> SourceBookRecord | None:
    book = payload.get("book")
    if not book or not isinstance(book, dict):
        return None

    title = book.get("title")
    title_long = book.get("title_long")

    authors = book.get("authors") or []
    subjects = book.get("subjects") or []

    return SourceBookRecord(
        source_name="isbndb",
        isbn=isbn,
        source_url=None,
        raw_source_payload=None,
        title=title_long or title,
        subtitle=_extract_subtitle(title, title_long),
        author=", ".join(authors) if authors else None,
        editorial=book.get("publisher"),
        synopsis=book.get("synopsis"),
        categories=subjects,
        cover_url=book.get("image"),
        language=normalize_language_code(book.get("language")),
    )
