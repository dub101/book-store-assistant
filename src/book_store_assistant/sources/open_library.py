import json

import httpx

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.issues import classify_http_issue, no_match_issue_code
from book_store_assistant.sources.open_library_parser import parse_open_library_payload
from book_store_assistant.sources.results import FetchResult


class OpenLibrarySource:
    source_name = "open_library"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def fetch_batch(self, isbns: list[str]) -> list[FetchResult]:
        if not isbns:
            return []

        try:
            response = httpx.get(
                self.config.open_library_api_base_url,
                params={
                    "bibkeys": ",".join(f"ISBN:{isbn}" for isbn in isbns),
                    "format": "json",
                    "jscmd": "data",
                },
                timeout=self.config.request_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            issue_codes = classify_http_issue(self.source_name, exc)
            return [
                FetchResult(
                    isbn=isbn,
                    record=None,
                    errors=[str(exc)],
                    issue_codes=issue_codes,
                    raw_payload=(
                        exc.response.text
                        if isinstance(exc, httpx.HTTPStatusError)
                        else None
                    ),
                )
                for isbn in isbns
            ]

        payload = response.json()
        raw_payload = json.dumps(payload, ensure_ascii=False)
        results: list[FetchResult] = []
        for isbn in isbns:
            record = parse_open_library_payload(payload, isbn)
            if record is None:
                results.append(
                    FetchResult(
                        isbn=isbn,
                        record=None,
                        errors=["No Open Library match found."],
                        issue_codes=[no_match_issue_code(self.source_name)],
                        raw_payload=raw_payload,
                    )
                )
                continue

            record = record.model_copy(update={"raw_source_payload": raw_payload})
            results.append(
                FetchResult(
                    isbn=isbn,
                    record=record,
                    errors=[],
                    raw_payload=raw_payload,
                )
            )

        return results

    def fetch(self, isbn: str) -> FetchResult:
        return self.fetch_batch([isbn])[0]
