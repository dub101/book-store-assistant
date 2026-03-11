import json
import time

import httpx

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.google_books_parser import parse_google_books_payload
from book_store_assistant.sources.issues import classify_http_issue, no_match_issue_code
from book_store_assistant.sources.results import FetchResult


class GoogleBooksSource:
    source_name = "google_books"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def _retry_delay_seconds(self, attempt: int, response: httpx.Response) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                parsed_retry_after = float(retry_after)
            except ValueError:
                pass
            else:
                if parsed_retry_after >= 0:
                    return parsed_retry_after

        return self.config.google_books_backoff_seconds * (2**attempt)

    def _should_retry(self, exc: httpx.HTTPStatusError, attempt: int) -> bool:
        return (
            exc.response.status_code == 429
            and attempt < self.config.google_books_max_retries
        )

    def fetch(self, isbn: str) -> FetchResult:
        """Fetch metadata for an ISBN from Google Books."""
        issue_codes: list[str] = []
        response: httpx.Response | None = None

        for attempt in range(self.config.google_books_max_retries + 1):
            try:
                response = httpx.get(
                    self.config.google_books_api_base_url,
                    params={"q": f"isbn:{isbn}"},
                    timeout=self.config.request_timeout_seconds,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                for issue_code in classify_http_issue(self.source_name, exc):
                    if issue_code not in issue_codes:
                        issue_codes.append(issue_code)

                if self._should_retry(exc, attempt):
                    time.sleep(self._retry_delay_seconds(attempt, exc.response))
                    continue

                return FetchResult(
                    isbn=isbn,
                    record=None,
                    errors=[str(exc)],
                    issue_codes=issue_codes,
                    raw_payload=exc.response.text,
                )
            except httpx.HTTPError as exc:
                return FetchResult(
                    isbn=isbn,
                    record=None,
                    errors=[str(exc)],
                    issue_codes=classify_http_issue(self.source_name, exc),
                )
            break

        if response is None:
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=["Google Books response was unavailable after retries."],
                issue_codes=issue_codes,
            )

        payload = response.json()
        raw_payload = json.dumps(payload, ensure_ascii=False)
        record = parse_google_books_payload(payload, isbn)
        if record is None:
            no_match_code = no_match_issue_code(self.source_name)
            result_issue_codes = (
                issue_codes
                if no_match_code in issue_codes
                else [*issue_codes, no_match_code]
            )
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=["No Google Books match found."],
                issue_codes=result_issue_codes,
                raw_payload=raw_payload,
            )

        record = record.model_copy(update={"raw_source_payload": raw_payload})
        return FetchResult(
            isbn=isbn,
            record=record,
            errors=[],
            issue_codes=issue_codes,
            raw_payload=raw_payload,
        )
