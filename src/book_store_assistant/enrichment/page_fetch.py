import json
import re
from html import unescape
from urllib.parse import urlparse

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

JSON_LD_SCRIPT_PATTERN = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)

BODY_DESCRIPTION_PATTERNS = (
    re.compile(
        r"<(?P<tag>div|section|p|span)[^>]*(?:id|class|data-testid|data-qa|itemprop)="
        r'["\'][^"\']*(?:description|synopsis|sinopsis|summary|resumen|about|'
        r'contracubierta|contra-cubierta|contra_cubierta|solapa|sobre(?:[-_ ]+el)?[-_ ]+libro|'
        r'book[-_ ]+description|descripcion(?:[-_ ]+del)?[-_ ]+libro)[^"\']*["\']'
        r"[^>]*>(?P<content>.*?)</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"<(?P<label_tag>h[1-6]|div|section|span|strong|b|p)[^>]*>"
        r"\s*(?:contracubierta|contra cubierta|solapa|sinopsis(?: del libro)?|"
        r"resumen|sobre el libro|acerca del libro)\s*</(?P=label_tag)>\s*"
        r"<(?P<content_tag>div|section|p|span)[^>]*>(?P<content>.*?)</(?P=content_tag)>",
        re.IGNORECASE | re.DOTALL,
    ),
)

SCRIPT_CONTENT_PATTERN = re.compile(
    r"<script[^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)

DESCRIPTION_TEXT_KEYS = {"description", "disambiguatingDescription"}
BOOKISH_TYPES = {"book", "product", "creativework", "bookseries"}
MIN_DESCRIPTION_LENGTH = 40

GOOGLE_BOOKS_EMBEDDED_PATTERNS = (
    re.compile(r'"description"\s*:\s*"((?:\\.|[^"\\])*)"', re.DOTALL),
    re.compile(
        r'"description"\s*:\s*\{\s*"simpleText"\s*:\s*"((?:\\.|[^"\\])*)"',
        re.DOTALL,
    ),
)

OPEN_LIBRARY_EMBEDDED_PATTERNS = (
    re.compile(r'"description"\s*:\s*"((?:\\.|[^"\\])*)"', re.DOTALL),
    re.compile(
        r'"description"\s*:\s*\{\s*"value"\s*:\s*"((?:\\.|[^"\\])*)"',
        re.DOTALL,
    ),
)


def _clean_text(text: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", text)
    normalized = re.sub(r"\s+", " ", unescape(without_tags)).strip()
    return normalized


def _append_candidate(
    candidates: list[tuple[str, str]],
    seen: set[str],
    kind: str,
    text: str,
) -> None:
    cleaned = _clean_text(text)
    if len(cleaned) < MIN_DESCRIPTION_LENGTH:
        return

    key = cleaned.casefold()
    if key in seen:
        return

    seen.add(key)
    candidates.append((kind, cleaned))


def _decode_quoted_json_string(value: str) -> str | None:
    try:
        decoded = json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return None

    if not isinstance(decoded, str):
        return None

    return decoded


def _looks_like_bookish_payload(data: dict) -> bool:
    raw_type = data.get("@type")
    if isinstance(raw_type, str):
        return raw_type.casefold() in BOOKISH_TYPES

    if isinstance(raw_type, list):
        return any(isinstance(item, str) and item.casefold() in BOOKISH_TYPES for item in raw_type)

    return False


def _collect_json_ld_descriptions(
    payload: object,
    candidates: list[tuple[str, str]],
    seen: set[str],
    parent_is_bookish: bool = False,
) -> None:
    if isinstance(payload, list):
        for item in payload:
            _collect_json_ld_descriptions(
                item,
                candidates,
                seen,
                parent_is_bookish=parent_is_bookish,
            )
        return

    if not isinstance(payload, dict):
        return

    is_bookish = parent_is_bookish or _looks_like_bookish_payload(payload)

    for key in DESCRIPTION_TEXT_KEYS:
        value = payload.get(key)
        if is_bookish and isinstance(value, str):
            _append_candidate(candidates, seen, "structured_data", value)

    graph = payload.get("@graph")
    if graph is not None:
        _collect_json_ld_descriptions(graph, candidates, seen, parent_is_bookish=parent_is_bookish)

    for value in payload.values():
        if isinstance(value, (dict, list)):
            _collect_json_ld_descriptions(value, candidates, seen, parent_is_bookish=is_bookish)


def _detect_source_host(source_url: str | None) -> str | None:
    if source_url is None:
        return None

    hostname = urlparse(source_url).hostname
    if hostname is None:
        return None

    normalized_host = hostname.casefold()
    if "google." in normalized_host:
        return "google_books"
    if normalized_host.endswith("openlibrary.org"):
        return "open_library"

    return None


def _collect_embedded_script_descriptions(
    html: str,
    kind: str,
    patterns: tuple[re.Pattern[str], ...],
    candidates: list[tuple[str, str]],
    seen: set[str],
) -> None:
    for script_match in SCRIPT_CONTENT_PATTERN.finditer(html):
        script_content = script_match.group(1)

        for pattern in patterns:
            for match in pattern.finditer(script_content):
                decoded = _decode_quoted_json_string(match.group(1))
                if decoded is None:
                    continue

                _append_candidate(candidates, seen, kind, decoded)


def _collect_source_specific_candidates(
    html: str,
    source_url: str | None,
    candidates: list[tuple[str, str]],
    seen: set[str],
) -> None:
    source_host = _detect_source_host(source_url)

    if source_host == "google_books":
        _collect_embedded_script_descriptions(
            html,
            "google_books_embedded_data",
            GOOGLE_BOOKS_EMBEDDED_PATTERNS,
            candidates,
            seen,
        )
        return

    if source_host == "open_library":
        _collect_embedded_script_descriptions(
            html,
            "open_library_embedded_data",
            OPEN_LIBRARY_EMBEDDED_PATTERNS,
            candidates,
            seen,
        )


def extract_description_candidates_from_html(
    html: str,
    source_url: str | None = None,
) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    for pattern in DESCRIPTION_PATTERNS:
        match = pattern.search(html)
        if match is None:
            continue

        _append_candidate(candidates, seen, "meta_description", match.group(1))

    for match in JSON_LD_SCRIPT_PATTERN.finditer(html):
        script_text = match.group(1).strip()
        if not script_text:
            continue

        try:
            payload = json.loads(unescape(script_text))
        except json.JSONDecodeError:
            continue

        _collect_json_ld_descriptions(payload, candidates, seen)

    for pattern in BODY_DESCRIPTION_PATTERNS:
        for match in pattern.finditer(html):
            _append_candidate(candidates, seen, "body_description", match.group("content"))

    _collect_source_specific_candidates(html, source_url, candidates, seen)

    return candidates
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
