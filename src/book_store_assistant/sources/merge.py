from book_store_assistant.sources.models import SourceBookRecord


SCALAR_FIELDS = [
    "title",
    "subtitle",
    "author",
    "editorial",
    "synopsis",
    "subject",
    "language",
]


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


def _seed_field_sources(record: SourceBookRecord) -> dict[str, str]:
    field_sources = dict(record.field_sources)

    for field_name in SCALAR_FIELDS:
        if getattr(record, field_name) and field_name not in field_sources:
            field_sources[field_name] = record.source_name

    if record.cover_url is not None and "cover_url" not in field_sources:
        field_sources["cover_url"] = record.source_name

    if record.categories and "categories" not in field_sources:
        field_sources["categories"] = record.source_name

    return field_sources


def _merge_scalar_field(
    merged: SourceBookRecord,
    record: SourceBookRecord,
    field_sources: dict[str, str],
    field_name: str,
) -> str | None:
    current_value = getattr(merged, field_name)
    if current_value:
        return current_value

    next_value = getattr(record, field_name)
    if next_value:
        field_sources[field_name] = record.source_name

    return next_value


def merge_source_records(records: list[SourceBookRecord]) -> SourceBookRecord:
    if not records:
        raise ValueError("merge_source_records requires at least one record.")

    merged = records[0].model_copy(deep=True)
    field_sources = _seed_field_sources(merged)

    for record in records[1:]:
        record_field_sources = _seed_field_sources(record)

        merged_values: dict[str, object] = {
            "source_name": _merge_source_names(merged.source_name, record.source_name),
            "isbn": merged.isbn,
            "categories": _merge_string_lists(merged.categories, record.categories),
            "cover_url": merged.cover_url or record.cover_url,
        }

        for field_name in SCALAR_FIELDS:
            merged_values[field_name] = _merge_scalar_field(merged, record, field_sources, field_name)

        if merged.cover_url is None and record.cover_url is not None:
            field_sources["cover_url"] = record.source_name
        elif merged.cover_url is not None and "cover_url" not in field_sources:
            field_sources["cover_url"] = merged.source_name

        merged_categories = merged_values["categories"]
        if isinstance(merged_categories, list) and merged_categories:
            merged_category_source = field_sources.get("categories")
            record_category_source = record_field_sources.get("categories")

            if merged_category_source and record_category_source:
                field_sources["categories"] = _merge_source_names(
                    merged_category_source,
                    record_category_source,
                )
            elif record_category_source:
                field_sources["categories"] = record_category_source
            elif merged_category_source:
                field_sources["categories"] = merged_category_source

        merged = SourceBookRecord(
            **merged_values,
            field_sources=field_sources,
        )

    return merged
