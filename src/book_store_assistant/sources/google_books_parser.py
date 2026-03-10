from book_store_assistant.sources.language_codes import normalize_language_code
from book_store_assistant.sources.models import SourceBookRecord


def parse_google_books_payload(payload: dict, isbn: str) -> SourceBookRecord | None:
    items = payload.get("items") or []
    if not items:
        return None

    volume_info = items[0].get("volumeInfo", {})

    authors = volume_info.get("authors") or []
    image_links = volume_info.get("imageLinks") or {}
    categories = volume_info.get("categories") or []

    return SourceBookRecord(
        source_name="google_books",
        isbn=isbn,
        source_url=volume_info.get("infoLink"),
        title=volume_info.get("title"),
        subtitle=volume_info.get("subtitle"),
        author=", ".join(authors) if authors else None,
        editorial=volume_info.get("publisher"),
        synopsis=volume_info.get("description"),
        categories=categories,
        cover_url=image_links.get("thumbnail"),
        language=normalize_language_code(volume_info.get("language")),
    )
