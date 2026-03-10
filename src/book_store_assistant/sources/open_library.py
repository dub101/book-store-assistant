import httpx

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.issues import classify_http_issue, no_match_issue_code
from book_store_assistant.sources.open_library_parser import parse_open_library_payload
from book_store_assistant.sources.results import FetchResult


class OpenLibrarySource:
    source_name = "open_library"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def fetch(self, isbn: str) -> FetchResult:
        try:
            response = httpx.get(
                self.config.open_library_api_base_url,
                params={
                    "bibkeys": f"ISBN:{isbn}",
                    "format": "json",
                    "jscmd": "data",
                },
                timeout=self.config.request_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=[str(exc)],
                issue_codes=classify_http_issue(self.source_name, exc),
            )

        record = parse_open_library_payload(response.json(), isbn)
        if record is None:
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=["No Open Library match found."],
                issue_codes=[no_match_issue_code(self.source_name)],
            )

        return FetchResult(isbn=isbn, record=record, errors=[])
