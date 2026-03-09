from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _merge_categories(primary: list[str], secondary: list[str]) -> list[str]:
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
        _merge_categories(
            [part.strip() for part in primary.split("+")],
            [part.strip() for part in secondary.split("+")],
        )
    )


def _merge_records(records: list[SourceBookRecord]) -> SourceBookRecord:
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
            categories=_merge_categories(merged.categories, record.categories),
            cover_url=merged.cover_url or record.cover_url,
            language=_first_non_empty(merged.language, record.language),
        )

    return merged


class FallbackMetadataSource:
    def __init__(self, sources: list[MetadataSource]) -> None:
        if not sources:
            raise ValueError("FallbackMetadataSource requires at least one source.")

        self.sources = sources

    def fetch(self, isbn: str) -> FetchResult:
        errors: list[str] = []
        seen_errors: set[str] = set()
        successful_records: list[SourceBookRecord] = []

        for source in self.sources:
            result = source.fetch(isbn)

            if result.record is not None:
                successful_records.append(result.record)

            source_name = getattr(source, "source_name", source.__class__.__name__)
            for error in result.errors:
                prefixed_error = f"{source_name}: {error}"
                if prefixed_error not in seen_errors:
                    seen_errors.add(prefixed_error)
                    errors.append(prefixed_error)

        if successful_records:
            return FetchResult(
                isbn=isbn,
                record=_merge_records(successful_records),
                errors=errors,
            )

        return FetchResult(isbn=isbn, record=None, errors=errors)
