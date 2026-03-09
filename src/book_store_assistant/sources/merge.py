from book_store_assistant.sources.models import SourceBookRecord


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _merge_string_lists(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for value in [*primary, *secondary]:
        normalized = value.strip()
        if not normalized:
            continue

        key = normalized.casefold()
        if key in seen:
            continue

        seen.add(key)
        merged.append(normalized)

    return merged


def _merge_source_names(primary: str, secondary: str) -> str:
    return " + ".join(
        _merge_string_lists(
            [part.strip() for part in primary.split("+")],
            [part.strip() for part in secondary.split("+")],
        )
    )


def merge_source_records(records: list[SourceBookRecord]) -> SourceBookRecord:
    if not records:
        raise ValueError("merge_source_records requires at least one record.")

    merged = records[0]

    for record in records[1:]:
        merged = SourceBookRecord(
            source_name=_merge_source_names(merged.source_name, record.source_name),
            isbn=merged.isbn,
            title=_first_non_empty(merged.title, record.title),
            subtitle=_first_non_empty(merged.subtitle, record.subtitle),
            author=_first_non_empty(merged.author, record.author),
            editorial=_first_non_empty(merged.editorial, record.editorial),
            synopsis=_first_non_empty(merged.synopsis, record.synopsis),
            subject=_first_non_empty(merged.subject, record.subject),
            categories=_merge_string_lists(merged.categories, record.categories),
            cover_url=merged.cover_url or record.cover_url,
            language=_first_non_empty(merged.language, record.language),
        )

    return merged
