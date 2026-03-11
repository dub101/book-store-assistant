import re
from html import unescape

from book_store_assistant.sources.language_codes import normalize_language_code
from book_store_assistant.sources.models import SourceBookRecord


def _extract_description(payload_item: dict, volume_info: dict) -> str | None:
    description = volume_info.get("description")
    if isinstance(description, str) and description.strip():
        return description.strip()

    search_info = payload_item.get("searchInfo")
    if not isinstance(search_info, dict):
        return None

    text_snippet = search_info.get("textSnippet")
    if not isinstance(text_snippet, str):
        return None

    cleaned = re.sub(r"<[^>]+>", " ", unescape(text_snippet))
    cleaned = " ".join(cleaned.split()).strip()
    return cleaned or None


def parse_google_books_payload(payload: dict, isbn: str) -> SourceBookRecord | None:
    items = payload.get("items") or []
    if not items:
        return None

    item = items[0]
    volume_info = item.get("volumeInfo", {})

    authors = volume_info.get("authors") or []
    image_links = volume_info.get("imageLinks") or {}
    categories = volume_info.get("categories") or []

    return SourceBookRecord(
        source_name="google_books",
        isbn=isbn,
        source_url=volume_info.get("infoLink"),
        raw_source_payload=None,
        title=volume_info.get("title"),
        subtitle=volume_info.get("subtitle"),
        author=", ".join(authors) if authors else None,
        editorial=volume_info.get("publisher"),
        synopsis=_extract_description(item, volume_info),
        categories=categories,
        cover_url=image_links.get("thumbnail"),
        language=normalize_language_code(volume_info.get("language")),
    )
