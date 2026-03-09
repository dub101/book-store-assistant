from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.results import FetchResult


class FallbackMetadataSource:
    def __init__(self, sources: list[MetadataSource]) -> None:
        if not sources:
            raise ValueError("FallbackMetadataSource requires at least one source.")

        self.sources = sources

    def fetch(self, isbn: str) -> FetchResult:
        errors: list[str] = []

        for source in self.sources:
            result = source.fetch(isbn)
            if result.record is not None:
                return result

            errors.extend(result.errors)

        return FetchResult(isbn=isbn, record=None, errors=errors)
