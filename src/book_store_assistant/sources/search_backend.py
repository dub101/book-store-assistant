import re
from collections.abc import Iterable
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse

import httpx

SEARCH_RESULT_LIMIT = 5
DUCKDUCKGO_HTML_SEARCH_URL = "https://html.duckduckgo.com/html/"
BING_SEARCH_URL = "https://www.bing.com/search"
BRAVE_SEARCH_URL = "https://search.brave.com/search"
YAHOO_SEARCH_URL = "https://search.yahoo.com/search"
RESULT_LINK_PATTERN = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"',
    re.IGNORECASE,
)
BING_RESULT_LINK_PATTERN = re.compile(
    r'<li[^>]+class="[^"]*b_algo[^"]*"[\s\S]*?<h2>\s*<a[^>]+href="([^"]+)"',
    re.IGNORECASE,
)
BRAVE_RESULT_LINK_PATTERN = re.compile(
    r'<a[^>]+href="(https?://[^"]+)"',
    re.IGNORECASE,
)
YAHOO_RESULT_LINK_PATTERN = re.compile(
    r'href="(https://r\.search\.yahoo\.com/[^"]+)"',
    re.IGNORECASE,
)
DEFAULT_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
DUCKDUCKGO_SEARCH_HEADERS = {
    **DEFAULT_BROWSER_HEADERS,
    "Referer": "https://duckduckgo.com/",
}
BING_SEARCH_HEADERS = {
    **DEFAULT_BROWSER_HEADERS,
    "Referer": "https://www.bing.com/",
}
BRAVE_SEARCH_HEADERS = {
    **DEFAULT_BROWSER_HEADERS,
    "Referer": "https://search.brave.com/",
}
YAHOO_SEARCH_HEADERS = {
    **DEFAULT_BROWSER_HEADERS,
    "Referer": "https://search.yahoo.com/",
}
IGNORED_RESULT_HOST_SUFFIXES = (
    "search.brave.com",
    "brave.com",
    "bravesoftware.com",
    "account.brave.com",
    "status.brave.app",
    "yahoo.com",
    "search.yahoo.com",
    "r.search.yahoo.com",
    "shopping.yahoo.com",
    "mail.yahoo.com",
    "finance.yahoo.com",
    "sports.yahoo.com",
    "r.bing.com",
    "bing.com",
)


def _decode_search_result_link(value: str) -> str | None:
    if value.startswith("//"):
        return _decode_search_result_link(f"https:{value}")

    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        query = parse_qs(parsed.query)
        for key in ("uddg", "u3"):
            redirected = query.get(key)
            if redirected:
                return unquote(redirected[0])
        if parsed.hostname and parsed.hostname.casefold().endswith("search.yahoo.com"):
            match = re.search(r"/RU=([^/]+)/RK=", value)
            if match is not None:
                return unquote(match.group(1))
        if parsed.hostname and parsed.hostname.casefold().endswith("duckduckgo.com"):
            return None
        return value

    return None


def _is_allowed_domain(url: str, allowed_domains: tuple[str, ...]) -> bool:
    if not allowed_domains:
        return True

    hostname = urlparse(url).hostname
    if hostname is None:
        return False

    normalized_hostname = hostname.casefold()
    normalized_domains = {domain.casefold() for domain in allowed_domains}
    return any(
        normalized_hostname == domain or normalized_hostname.endswith(f".{domain}")
        for domain in normalized_domains
    )


class SearchBackend:
    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = SEARCH_RESULT_LIMIT,
    ) -> list[str]:
        raise NotImplementedError


class PageContentFetcher:
    def fetch_text(self, url: str) -> str | None:
        raise NotImplementedError


def _build_search_query(query: str, allowed_domains: tuple[str, ...]) -> str:
    domain_query = " OR ".join(f"site:{domain}" for domain in allowed_domains)
    return f"{query} ({domain_query})" if domain_query else query


class DuckDuckGoHtmlSearcher(SearchBackend):
    def __init__(self, timeout_seconds: float, client: httpx.Client | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.client = client

    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = SEARCH_RESULT_LIMIT,
    ) -> list[str]:
        client = self.client or httpx.Client()
        response = client.get(
            DUCKDUCKGO_HTML_SEARCH_URL,
            params={"q": _build_search_query(query, allowed_domains)},
            headers=DUCKDUCKGO_SEARCH_HEADERS,
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()

        return _extract_search_result_links(
            response.text,
            allowed_domains=allowed_domains,
            limit=limit,
        )


class BingHtmlSearcher(SearchBackend):
    def __init__(self, timeout_seconds: float, client: httpx.Client | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.client = client

    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = SEARCH_RESULT_LIMIT,
    ) -> list[str]:
        client = self.client or httpx.Client()
        response = client.get(
            BING_SEARCH_URL,
            params={"q": _build_search_query(query, allowed_domains), "setlang": "es"},
            headers=BING_SEARCH_HEADERS,
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()

        return _extract_bing_result_links(
            response.text,
            allowed_domains=allowed_domains,
            limit=limit,
        )


class BraveHtmlSearcher(SearchBackend):
    def __init__(self, timeout_seconds: float, client: httpx.Client | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.client = client

    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = SEARCH_RESULT_LIMIT,
    ) -> list[str]:
        client = self.client or httpx.Client()
        response = client.get(
            BRAVE_SEARCH_URL,
            params={"q": _build_search_query(query, allowed_domains)},
            headers=BRAVE_SEARCH_HEADERS,
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()

        return _extract_brave_result_links(
            response.text,
            allowed_domains=allowed_domains,
            limit=limit,
        )


class YahooHtmlSearcher(SearchBackend):
    def __init__(self, timeout_seconds: float, client: httpx.Client | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.client = client

    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = SEARCH_RESULT_LIMIT,
    ) -> list[str]:
        client = self.client or httpx.Client()
        response = client.get(
            YAHOO_SEARCH_URL,
            params={"p": _build_search_query(query, allowed_domains)},
            headers=YAHOO_SEARCH_HEADERS,
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()

        return _extract_yahoo_result_links(
            response.text,
            allowed_domains=allowed_domains,
            limit=limit,
        )


class FallbackSearchBackend(SearchBackend):
    def __init__(self, backends: list[SearchBackend]) -> None:
        self.backends = backends

    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = SEARCH_RESULT_LIMIT,
    ) -> list[str]:
        last_error: Exception | None = None
        for backend in self.backends:
            try:
                results = backend.search(query, allowed_domains, limit)
            except httpx.HTTPError as exc:
                last_error = exc
                continue
            if results:
                return results
        if last_error is not None:
            raise last_error
        return []


def _extract_search_result_links(
    html: str,
    *,
    allowed_domains: Iterable[str],
    limit: int,
) -> list[str]:
    normalized_allowed_domains = tuple(allowed_domains)
    links: list[str] = []
    seen: set[str] = set()

    for match in RESULT_LINK_PATTERN.finditer(html):
        link = _decode_search_result_link(unescape(match.group(1)))
        if link is None or not _is_allowed_domain(link, normalized_allowed_domains):
            continue

        if link in seen:
            continue

        seen.add(link)
        links.append(link)
        if len(links) >= limit:
            break

    return links


def _extract_bing_result_links(
    html: str,
    *,
    allowed_domains: Iterable[str],
    limit: int,
) -> list[str]:
    normalized_allowed_domains = tuple(allowed_domains)
    links: list[str] = []
    seen: set[str] = set()

    for match in BING_RESULT_LINK_PATTERN.finditer(html):
        link = _decode_search_result_link(unescape(match.group(1)))
        if link is None or not _is_allowed_domain(link, normalized_allowed_domains):
            continue
        if link in seen:
            continue
        seen.add(link)
        links.append(link)
        if len(links) >= limit:
            break

    return links


def _is_ignored_result_link(url: str) -> bool:
    hostname = urlparse(url).hostname
    if hostname is None:
        return True

    normalized_hostname = hostname.casefold()
    return any(
        normalized_hostname == suffix
        or normalized_hostname.endswith(f".{suffix}")
        for suffix in IGNORED_RESULT_HOST_SUFFIXES
    )


def _extract_brave_result_links(
    html: str,
    *,
    allowed_domains: Iterable[str],
    limit: int,
) -> list[str]:
    normalized_allowed_domains = tuple(allowed_domains)
    links: list[str] = []
    seen: set[str] = set()

    for match in BRAVE_RESULT_LINK_PATTERN.finditer(html):
        link = _decode_search_result_link(unescape(match.group(1)))
        if (
            link is None
            or _is_ignored_result_link(link)
            or not _is_allowed_domain(link, normalized_allowed_domains)
        ):
            continue
        if link in seen:
            continue
        seen.add(link)
        links.append(link)
        if len(links) >= limit:
            break

    return links


def _extract_yahoo_result_links(
    html: str,
    *,
    allowed_domains: Iterable[str],
    limit: int,
) -> list[str]:
    normalized_allowed_domains = tuple(allowed_domains)
    links: list[str] = []
    seen: set[str] = set()

    for match in YAHOO_RESULT_LINK_PATTERN.finditer(html):
        link = _decode_search_result_link(unescape(match.group(1)))
        if (
            link is None
            or _is_ignored_result_link(link)
            or not _is_allowed_domain(link, normalized_allowed_domains)
        ):
            continue
        if link in seen:
            continue
        seen.add(link)
        links.append(link)
        if len(links) >= limit:
            break

    return links


def build_default_search_backend(
    timeout_seconds: float,
    client: httpx.Client | None = None,
) -> SearchBackend:
    return FallbackSearchBackend(
        [
            YahooHtmlSearcher(timeout_seconds, client=client),
            DuckDuckGoHtmlSearcher(timeout_seconds, client=client),
            BingHtmlSearcher(timeout_seconds, client=client),
        ]
    )
