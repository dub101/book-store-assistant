from book_store_assistant.sources.models import SourceBookRecord


LANGUAGE_CODE_MAP = {
    "spa": "es",
    "eng": "en",
}


def _normalize_language(language: str | None) -> str | None:
    if language is None:
        return None

    normalized = language.strip().lower()
    return LANGUAGE_CODE_MAP.get(normalized, normalized or None)


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
        title=volume_info.get("title"),
        subtitle=volume_info.get("subtitle"),
        author=", ".join(authors) if authors else None,
        editorial=volume_info.get("publisher"),
        synopsis=volume_info.get("description"),
        categories=categories,
        cover_url=image_links.get("thumbnail"),
        language=_normalize_language(volume_info.get("language")),
    )
