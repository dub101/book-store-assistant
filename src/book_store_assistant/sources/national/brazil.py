import json

import httpx

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.issues import classify_http_issue, no_match_issue_code
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult

_BASE_URL = "https://brasilapi.com.br/api/isbn/v1"


class BrazilISBNSource:
    source_name = "brazil_isbn"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def fetch(self, isbn: str) -> FetchResult:
        url = f"{_BASE_URL}/{isbn}"
        try:
            response = httpx.get(
                url,
                timeout=self.config.request_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=[str(exc)],
                issue_codes=classify_http_issue(self.source_name, exc),
                raw_payload=(
                    exc.response.text
                    if isinstance(exc, httpx.HTTPStatusError)
                    else None
                ),
            )

        raw_text = response.text
        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError):
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=["Invalid JSON in BrasilAPI response"],
                issue_codes=[no_match_issue_code(self.source_name)],
                raw_payload=raw_text,
            )

        title = data.get("titulo") or data.get("title")
        authors_raw = data.get("autores") or data.get("authors") or []
        if isinstance(authors_raw, list):
            author = "; ".join(str(a) for a in authors_raw if a) or None
        else:
            author = str(authors_raw) if authors_raw else None
        editorial = data.get("editora") or data.get("publisher")

        if not any([title, author, editorial]):
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=[],
                issue_codes=[no_match_issue_code(self.source_name)],
                raw_payload=raw_text,
            )

        from pydantic import HttpUrl

        record = SourceBookRecord(
            source_name=self.source_name,
            isbn=isbn,
            source_url=HttpUrl(url),
            title=title,
            author=author,
            editorial=editorial,
            raw_source_payload=raw_text,
        )

        return FetchResult(
            isbn=isbn,
            record=record,
            errors=[],
            issue_codes=[],
            raw_payload=raw_text,
        )
