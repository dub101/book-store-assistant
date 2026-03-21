from typing import TypeVar

from book_store_assistant.sources.confidence import source_confidence
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
FieldValue = TypeVar("FieldValue")


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

    if record.source_url is not None and "source_url" not in field_sources:
        field_sources["source_url"] = record.source_name

    if record.categories and "categories" not in field_sources:
        field_sources["categories"] = record.source_name

    return field_sources


def _seed_field_confidence(
    record: SourceBookRecord,
    field_sources: dict[str, str],
) -> dict[str, float]:
    field_confidence = dict(record.field_confidence)

    for field_name in [*SCALAR_FIELDS, "cover_url", "source_url", "categories"]:
        field_value = getattr(record, field_name)
        if not field_value or field_name in field_confidence:
            continue

        source_name = field_sources.get(field_name, record.source_name)
        field_confidence[field_name] = source_confidence(source_name)

    return field_confidence


def _merge_scalar_field(
    merged: SourceBookRecord,
    record: SourceBookRecord,
    field_sources: dict[str, str],
    field_confidence: dict[str, float],
    record_field_sources: dict[str, str],
    record_field_confidence: dict[str, float],
    field_name: str,
) -> FieldValue | None:
    current_value = getattr(merged, field_name)
    next_value = getattr(record, field_name)
    if not current_value:
        if next_value:
            field_sources[field_name] = record_field_sources.get(field_name, record.source_name)
            field_confidence[field_name] = record_field_confidence.get(
                field_name,
                source_confidence(record.source_name),
            )
        return next_value

    if not next_value:
        return current_value

    current_confidence = field_confidence.get(
        field_name,
        source_confidence(field_sources.get(field_name, merged.source_name)),
    )
    next_confidence = record_field_confidence.get(
        field_name,
        source_confidence(record_field_sources.get(field_name, record.source_name)),
    )
    if next_confidence > current_confidence:
        field_sources[field_name] = record_field_sources.get(field_name, record.source_name)
        field_confidence[field_name] = next_confidence
        return next_value

    field_confidence[field_name] = current_confidence
    return current_value


def merge_source_records(records: list[SourceBookRecord]) -> SourceBookRecord:
    if not records:
        raise ValueError("merge_source_records requires at least one record.")

    merged = records[0].model_copy(deep=True)
    field_sources = _seed_field_sources(merged)
    field_confidence = _seed_field_confidence(merged, field_sources)
    merged = merged.model_copy(
        update={
            "field_sources": field_sources,
            "field_confidence": field_confidence,
        }
    )

    for record in records[1:]:
        record_field_sources = _seed_field_sources(record)
        record_field_confidence = _seed_field_confidence(record, record_field_sources)

        source_name = _merge_source_names(merged.source_name, record.source_name)
        categories = _merge_string_lists(merged.categories, record.categories)
        title = _merge_scalar_field(
            merged,
            record,
            field_sources,
            field_confidence,
            record_field_sources,
            record_field_confidence,
            "title",
        )
        subtitle = _merge_scalar_field(
            merged,
            record,
            field_sources,
            field_confidence,
            record_field_sources,
            record_field_confidence,
            "subtitle",
        )
        author = _merge_scalar_field(
            merged,
            record,
            field_sources,
            field_confidence,
            record_field_sources,
            record_field_confidence,
            "author",
        )
        editorial = _merge_scalar_field(
            merged,
            record,
            field_sources,
            field_confidence,
            record_field_sources,
            record_field_confidence,
            "editorial",
        )
        synopsis = _merge_scalar_field(
            merged,
            record,
            field_sources,
            field_confidence,
            record_field_sources,
            record_field_confidence,
            "synopsis",
        )
        subject = _merge_scalar_field(
            merged,
            record,
            field_sources,
            field_confidence,
            record_field_sources,
            record_field_confidence,
            "subject",
        )
        language = _merge_scalar_field(
            merged,
            record,
            field_sources,
            field_confidence,
            record_field_sources,
            record_field_confidence,
            "language",
        )
        cover_url = _merge_scalar_field(
            merged,
            record,
            field_sources,
            field_confidence,
            record_field_sources,
            record_field_confidence,
            "cover_url",
        )
        source_url = _merge_scalar_field(
            merged,
            record,
            field_sources,
            field_confidence,
            record_field_sources,
            record_field_confidence,
            "source_url",
        )

        if categories:
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

            field_confidence["categories"] = max(
                field_confidence.get(
                    "categories",
                    source_confidence(merged_category_source or merged.source_name),
                ),
                record_field_confidence.get(
                    "categories",
                    source_confidence(record_category_source or record.source_name),
                ),
            )

        merged = SourceBookRecord(
            source_name=source_name,
            isbn=merged.isbn,
            source_url=source_url,
            title=title,
            subtitle=subtitle,
            author=author,
            editorial=editorial,
            synopsis=synopsis,
            subject=subject,
            categories=categories,
            cover_url=cover_url,
            language=language,
            field_sources=field_sources,
            field_confidence=field_confidence,
        )

    return merged
