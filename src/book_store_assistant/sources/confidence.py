def _normalize_source_name(source_name: str) -> str:
    return source_name.strip().casefold()


def source_confidence(source_name: str) -> float:
    normalized = _normalize_source_name(source_name)

    if "publisher_page" in normalized:
        return 1.0
    if "retailer_page" in normalized:
        return 0.55
    if "web_search_official" in normalized:
        return 0.98
    if "web_search" in normalized:
        return 0.85
    if normalized == "bne":
        return 1.0
    if normalized == "isbndb":
        return 0.9
    if normalized == "open_library":
        return 0.6
    if normalized == "google_books":
        return 0.75
    if normalized == "ai_enriched":
        return 0.3
    if normalized == "fetch_error":
        return 0.0

    if "+" in normalized:
        parts = [part.strip() for part in normalized.split("+")]
        return max((source_confidence(part) for part in parts), default=0.0)

    return 0.5
