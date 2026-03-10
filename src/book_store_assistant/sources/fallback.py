from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.merge import merge_source_records
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


class FallbackMetadataSource:
    def __init__(self, sources: list[MetadataSource]) -> None:
        if not sources:
            raise ValueError("FallbackMetadataSource requires at least one source.")

        self.sources = sources

    def fetch(self, isbn: str) -> FetchResult:
        errors: list[str] = []
        issue_codes: list[str] = []
        seen_errors: set[str] = set()
        seen_issue_codes: set[str] = set()
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

            for issue_code in result.issue_codes:
                prefixed_issue_code = f"{source_name.upper()}:{issue_code}"
                if prefixed_issue_code not in seen_issue_codes:
                    seen_issue_codes.add(prefixed_issue_code)
                    issue_codes.append(prefixed_issue_code)

        if successful_records:
            return FetchResult(
                isbn=isbn,
                record=merge_source_records(successful_records),
                errors=errors,
                issue_codes=issue_codes,
            )

        return FetchResult(isbn=isbn, record=None, errors=errors, issue_codes=issue_codes)
