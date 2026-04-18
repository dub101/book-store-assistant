import httpx
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

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
                raw_payload=exc.response.text if isinstance(exc, httpx.HTTPStatusError) else None,
            )

        try:
            record = parse_bne_sru_payload(response.text, isbn)
        except (ET.ParseError, DefusedXmlException):
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=["Invalid BNE SRU response payload."],
                issue_codes=["BNE_FETCH_ERROR"],
                raw_payload=response.text,
            )

        if record is None:
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=["No BNE match found."],
                issue_codes=[no_match_issue_code(self.source_name)],
                raw_payload=response.text,
            )

        record = record.model_copy(update={"raw_source_payload": response.text})
        return FetchResult(
            isbn=isbn,
            record=record,
            errors=[],
            issue_codes=[],
            raw_payload=response.text,
        )
