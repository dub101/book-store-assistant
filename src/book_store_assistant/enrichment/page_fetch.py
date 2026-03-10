import re

import httpx

DESCRIPTION_PATTERNS = (
    re.compile(
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        re.IGNORECASE | re.DOTALL,
    ),
)


def extract_description_from_html(html: str) -> str | None:
    for pattern in DESCRIPTION_PATTERNS:
        match = pattern.search(html)
        if match is None:
            continue

        description = re.sub(r"\s+", " ", match.group(1)).strip()
        if description:
            return description

    return None


class HttpPageContentFetcher:
    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_text(self, url: str) -> str | None:
        try:
            response = httpx.get(url, timeout=self.timeout_seconds, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        return response.text
