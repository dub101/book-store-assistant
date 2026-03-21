from collections.abc import Iterable

from book_store_assistant.sources.confidence import source_confidence
from book_store_assistant.sources.models import FieldCandidate, SourceBookRecord

CANDIDATE_FIELDS = ("title", "subtitle", "author", "editorial", "synopsis", "subject")


def _normalize_candidate_value(value: str) -> str:
    return " ".join(value.split()).strip()


def _candidate_key(candidate: FieldCandidate) -> tuple[str, str, str]:
    return (
        candidate.field_name,
        candidate.source_name.casefold(),
        candidate.value.casefold(),
    )


def _merge_candidates(
    existing: Iterable[FieldCandidate],
    new_items: Iterable[FieldCandidate],
) -> list[FieldCandidate]:
    merged: list[FieldCandidate] = []
    best_by_key: dict[tuple[str, str, str], FieldCandidate] = {}
    merged_keys: set[tuple[str, str, str]] = set()

    for candidate in [*existing, *new_items]:
        key = _candidate_key(candidate)
        previous = best_by_key.get(key)
        if previous is None or candidate.confidence > previous.confidence:
            best_by_key[key] = candidate

    for candidate in [*existing, *new_items]:
        key = _candidate_key(candidate)
        if key in merged_keys:
            continue
        merged_keys.add(key)
        merged.append(best_by_key[key])

    return merged


def build_seeded_candidates(record: SourceBookRecord) -> dict[str, list[FieldCandidate]]:
    seeded = {field_name: list(items) for field_name, items in record.field_candidates.items()}

    for field_name in CANDIDATE_FIELDS:
        field_value = getattr(record, field_name)
        if not isinstance(field_value, str):
            continue

        normalized_value = _normalize_candidate_value(field_value)
        if not normalized_value:
            continue

        source_name = record.field_sources.get(field_name, record.source_name)
        candidate = FieldCandidate(
            field_name=field_name,
            value=normalized_value,
            source_name=source_name,
            confidence=record.field_confidence.get(
                field_name,
                source_confidence(source_name),
            ),
            language=record.language if field_name == "synopsis" else None,
            source_url=record.source_url,
            extraction_method=f"source_{field_name}_field",
        )
        seeded[field_name] = _merge_candidates(seeded.get(field_name, []), [candidate])

    return seeded


def merge_field_candidate_maps(
    primary: dict[str, list[FieldCandidate]],
    secondary: dict[str, list[FieldCandidate]],
) -> dict[str, list[FieldCandidate]]:
    merged: dict[str, list[FieldCandidate]] = {}

    for field_name in sorted({*primary.keys(), *secondary.keys()}):
        merged[field_name] = _merge_candidates(
            primary.get(field_name, []),
            secondary.get(field_name, []),
        )

    return merged


def get_field_candidates(record: SourceBookRecord, field_name: str) -> list[FieldCandidate]:
    return build_seeded_candidates(record).get(field_name, [])
