import json
import time

import httpx

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.isbndb_parser import parse_isbndb_payload
from book_store_assistant.sources.issues import classify_http_issue, no_match_issue_code
from book_store_assistant.sources.results import FetchResult


class ISBNdbSource:
    source_name = "isbndb"
    max_retries = 3

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()
        self._backoff_seconds = 0.0

    @property
    def adaptive_pause(self) -> float:
        return max(self.config.source_request_pause_seconds, self._backoff_seconds)

    def _retry_delay(self, attempt: int, response: httpx.Response) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(float(retry_after), 1.0)
            except ValueError:
                pass
        return 2.0 * (2 ** attempt)

    def fetch(self, isbn: str) -> FetchResult:
        """Fetch metadata for an ISBN from ISBNdb."""
        if self.config.isbndb_api_key is None:
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=["ISBNdb API key not configured."],
                issue_codes=["ISBNDB_NO_API_KEY"],
            )

        issue_codes: list[str] = []
        response: httpx.Response | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = httpx.get(
                    f"https://api2.isbndb.com/book/{isbn}",
                    headers={"Authorization": self.config.isbndb_api_key},
                    timeout=self.config.request_timeout_seconds,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                for issue_code in classify_http_issue(self.source_name, exc):
                    if issue_code not in issue_codes:
                        issue_codes.append(issue_code)

                if exc.response.status_code == 429 and attempt < self.max_retries:
                    delay = self._retry_delay(attempt, exc.response)
                    self._backoff_seconds = max(self._backoff_seconds, 0.5)
                    time.sleep(delay)
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
                errors=["ISBNdb response was unavailable after retries."],
                issue_codes=issue_codes,
            )

        payload = response.json()
        raw_payload = json.dumps(payload, ensure_ascii=False)
        record = parse_isbndb_payload(payload, isbn)
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
                errors=["No ISBNdb match found."],
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
