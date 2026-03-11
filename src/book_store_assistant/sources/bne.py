import xml.etree.ElementTree as ET

import httpx

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.bne_parser import parse_bne_sru_payload
from book_store_assistant.sources.issues import classify_http_issue, no_match_issue_code
from book_store_assistant.sources.results import FetchResult


class BneSruSource:
    source_name = "bne"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def fetch(self, isbn: str) -> FetchResult:
        try:
            response = httpx.get(
                self.config.bne_sru_base_url,
                params={
                    "operation": "searchRetrieve",
                    "version": "1.2",
                    "query": f'alma.isbn="{isbn}"',
                    "recordSchema": "dc",
                    "maximumRecords": 1,
                    "startRecord": 1,
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

        try:
            record = parse_bne_sru_payload(response.text, isbn)
        except ET.ParseError:
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=["Invalid BNE SRU response payload."],
                issue_codes=["BNE_FETCH_ERROR"],
            )

        if record is None:
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=["No BNE match found."],
                issue_codes=[no_match_issue_code(self.source_name)],
            )

        return FetchResult(isbn=isbn, record=record, errors=[], issue_codes=[])
