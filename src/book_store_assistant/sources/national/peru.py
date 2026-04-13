import re

import httpx

from book_store_assistant.config import AppConfig
from book_store_assistant.sources.issues import classify_http_issue, no_match_issue_code
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult

_BASE_URL = "https://isbn.bnp.gob.pe/catalogo.php"


def _extract_field(html: str, label: str) -> str | None:
    """Try to pull a labelled value from the detail page HTML.

    The public catalogue renders rows like:
        <b>Titulo:</b>&nbsp;Some Title<br>
    or inside table cells.  We attempt a generous regex that handles
    both patterns.  If the site layout changes this will simply return
    ``None`` and the source degrades gracefully.
    """
    pattern = re.compile(
        rf"<b>\s*{re.escape(label)}\s*:?\s*</b>\s*(?:&nbsp;|\s)*(.+?)(?:<br|</td|</tr|<b>)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(html)
    if match is None:
        return None
    value = re.sub(r"<[^>]+>", "", match.group(1)).strip()
    return value if value else None


class PeruISBNSource:
    source_name = "peru_isbn"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def fetch(self, isbn: str) -> FetchResult:
        url = f"{_BASE_URL}?mode=detalle&isbn={isbn}"
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

        html = response.text

        title = _extract_field(html, "T[ií]tulo") or _extract_field(html, "Titulo")
        author = _extract_field(html, "Autor")
        editorial = (
            _extract_field(html, "Editorial")
            or _extract_field(html, "Sello")
        )

        if not any([title, author, editorial]):
            return FetchResult(
                isbn=isbn,
                record=None,
                errors=[],
                issue_codes=[no_match_issue_code(self.source_name)],
                raw_payload=html,
            )

        from pydantic import HttpUrl

        record = SourceBookRecord(
            source_name=self.source_name,
            isbn=isbn,
            source_url=HttpUrl(url),
            title=title,
            author=author,
            editorial=editorial,
            raw_source_payload=html,
        )

        return FetchResult(
            isbn=isbn,
            record=record,
            errors=[],
            issue_codes=[],
            raw_payload=html,
        )
