from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.results import FetchResult


class FallbackMetadataSource:
    def __init__(self, sources: list[MetadataSource]) -> None:
        if not sources:
            raise ValueError("FallbackMetadataSource requires at least one source.")

        self.sources = sources

    def fetch(self, isbn: str) -> FetchResult:
        errors: list[str] = []
        seen_errors: set[str] = set()

        for source in self.sources:
            result = source.fetch(isbn)
            if result.record is not None:
                return result

            source_name = getattr(source, "source_name", source.__class__.__name__)
            for error in result.errors:
                prefixed_error = f"{source_name}: {error}"
                if prefixed_error not in seen_errors:
                    seen_errors.add(prefixed_error)
                    errors.append(prefixed_error)

        return FetchResult(isbn=isbn, record=None, errors=errors)
