import httpx

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.google_books_parser import parse_google_books_payload
from book_store_assistant.sources.results import FetchResult


class GoogleBooksSource:
    source_name = "google_books"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def fetch(self, isbn: str) -> FetchResult:
        """Fetch metadata for an ISBN from Google Books."""
        try:
            response = httpx.get(
                self.config.google_books_api_base_url,
                params={"q": f"isbn:{isbn}"},
                timeout=self.config.request_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return FetchResult(isbn=isbn, record=None, errors=[str(exc)])

        record = parse_google_books_payload(response.json(), isbn)
        if record is None:
            return FetchResult(isbn=isbn, record=None, errors=["No Google Books match found."])

        return FetchResult(isbn=isbn, record=record, errors=[])
