from book_store_assistant.sources.models import SourceBookRecord


def _extract_description(data: dict) -> str | None:
    description = data.get("description")

    if isinstance(description, str):
        return description

    if isinstance(description, dict):
        value = description.get("value")
        if isinstance(value, str):
            return value

    return None


def parse_open_library_payload(payload: dict, isbn: str) -> SourceBookRecord | None:
    data = payload.get(f"ISBN:{isbn}")
    if not data:
        return None

    authors = data.get("authors") or []
    author_names = [author.get("name") for author in authors if author.get("name")]

    publishers = data.get("publishers") or []
    publisher_names = [publisher.get("name") for publisher in publishers if publisher.get("name")]

    subjects = data.get("subjects") or []
    subject_names = [subject.get("name") for subject in subjects if subject.get("name")]

    cover = data.get("cover") or {}

    return SourceBookRecord(
        source_name="open_library",
        isbn=isbn,
        title=data.get("title"),
        subtitle=data.get("subtitle"),
        author=", ".join(author_names) if author_names else None,
        editorial=", ".join(publisher_names) if publisher_names else None,
        synopsis=_extract_description(data),
        categories=subject_names,
        cover_url=cover.get("large") or cover.get("medium") or cover.get("small"),
    )
