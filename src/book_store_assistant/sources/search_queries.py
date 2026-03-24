import re
from html import unescape

from book_store_assistant.sources.models import SourceBookRecord

QUERY_TEXT_ARTIFACT_PATTERN = re.compile(r"\[[^\]]+\]")


def clean_query_text(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = QUERY_TEXT_ARTIFACT_PATTERN.sub(" ", value)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = cleaned.replace('"', " ").replace("'", " ")
    cleaned = " ".join(cleaned.split()).strip()
    return cleaned or None


def editorial_query_terms(value: str | None) -> list[str]:
    cleaned = clean_query_text(value)
    if cleaned is None:
        return []

    terms = [cleaned]
    for segment in re.split(r"[,/;|&()\[\]]+", cleaned):
        normalized = clean_query_text(segment)
        if normalized is None or normalized in terms:
            continue
        terms.append(normalized)

    return terms


def append_query(queries: list[str], *parts: str | None) -> None:
    terms = [part for part in parts if isinstance(part, str) and part.strip()]
    if not terms:
        return

    query = " ".join(f'"{term}"' for term in terms)
    if query not in queries:
        queries.append(query)


def append_query_text(queries: list[str], query: str | None) -> None:
    if query is None:
        return

    cleaned = " ".join(query.split()).strip()
    if cleaned and cleaned not in queries:
        queries.append(cleaned)


def build_contextual_isbn_queries(
    record: SourceBookRecord,
    *,
    max_editorial_terms: int = 3,
) -> list[str]:
    title = clean_query_text(record.title)
    subtitle = clean_query_text(record.subtitle)
    author = clean_query_text(record.author)
    editorial_terms = editorial_query_terms(record.editorial)

    queries: list[str] = []
    append_query(queries, record.isbn, title, author)
    append_query(queries, record.isbn)
    append_query(queries, record.isbn, title, subtitle, author)
    append_query(queries, record.isbn, title)
    append_query(queries, record.isbn, author)
    append_query(queries, record.isbn, subtitle)

    for editorial in editorial_terms[:max_editorial_terms]:
        append_query(queries, record.isbn, title, editorial)
        append_query(queries, record.isbn, title, subtitle, editorial)
        append_query(queries, record.isbn, author, editorial)
        append_query(queries, record.isbn, editorial)

    return queries


def build_editorial_discovery_queries(record: SourceBookRecord) -> list[str]:
    title = clean_query_text(record.title)
    subtitle = clean_query_text(record.subtitle)
    author = clean_query_text(record.author)

    queries: list[str] = []
    extra_parts = [
        f"titulo {title}" if title else None,
        f"subtitulo {subtitle}" if subtitle else None,
        f"autor {author}" if author else None,
    ]
    extra_info = "; ".join(part for part in extra_parts if part)
    natural_language_query = f"Editorial del libro con isbn {record.isbn}"
    if extra_info:
        natural_language_query = (
            f"{natural_language_query} y informacion extra: {extra_info}"
        )

    append_query_text(queries, natural_language_query)
    append_query(queries, record.isbn, "editorial")
    append_query(queries, record.isbn, title)
    append_query(queries, record.isbn)
    append_query(queries, record.isbn, title, author)
    append_query(queries, record.isbn, author)
    append_query(queries, record.isbn, title, subtitle)
    append_query(queries, record.isbn, subtitle)
    return queries
