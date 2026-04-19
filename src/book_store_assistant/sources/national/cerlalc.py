"""Generic CERLALC-style HTML catalogue scraper.

Most Latin American ISBN agencies expose a CERLALC-based catalogue with a
consistent HTML layout.  This module provides a single parameterized source
class so individual country modules only need to declare their configuration.
"""

import re

import httpx
from pydantic import HttpUrl

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.issues import classify_http_issue, no_match_issue_code
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


def extract_field(html: str, label: str) -> str | None:
    """Pull a labelled value from a CERLALC catalogue HTML page."""
    pattern = re.compile(
        rf"<b>\s*{re.escape(label)}\s*:?\s*</b>\s*(?:&nbsp;|\s)*(.+?)(?:<br|</td|</tr|<b>)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(html)
    if match is None:
        return None
    value = re.sub(r"<[^>]+>", "", match.group(1)).strip()
    return value if value else None


class CerlalcHtmlSource:
    """Scrapes a CERLALC-style ISBN catalogue page.

    Subclasses only need to set class variables:
        source_name      – e.g. ``"colombia_isbn"``
        base_url         – e.g. ``"https://isbn.camlibro.com.co/catalogo.php"``
        editorial_labels – ordered fallback labels for the editorial field
        url_template     – format string with ``{base_url}`` and ``{isbn}``
    """

    source_name: str = ""
    base_url: str = ""
    editorial_labels: tuple[str, ...] = ("Editorial",)
    url_template: str = "{base_url}?mode=detalle&isbn={isbn}"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def _build_url(self, isbn: str) -> str:
        return self.url_template.format(base_url=self.base_url, isbn=isbn)

    def fetch(self, isbn: str) -> FetchResult:
        url = self._build_url(isbn)
        try:
            response = httpx.get(url, timeout=self.config.request_timeout_seconds)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=[str(exc)],
                issue_codes=classify_http_issue(self.source_name, exc),
                raw_payload=(
                    exc.response.text if isinstance(exc, httpx.HTTPStatusError) else None
                ),
            )

        html = response.text

        title = extract_field(html, "T[ií]tulo") or extract_field(html, "Titulo")
        author = extract_field(html, "Autor")
        editorial: str | None = None
        for label in self.editorial_labels:
            editorial = extract_field(html, label)
            if editorial:
                break

        if not any([title, author, editorial]):
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=[],
                issue_codes=[no_match_issue_code(self.source_name)],
                raw_payload=html,
            )

        record = SourceBookRecord(
            source_name=self.source_name,
            isbn=isbn,
            source_url=HttpUrl(url),
            title=title,
            author=author,
            editorial=editorial,
            raw_source_payload=html,
        )

        return FetchResult(isbn=isbn, record=record, errors=[], issue_codes=[], raw_payload=html)
