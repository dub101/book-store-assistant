import json
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from pydantic import HttpUrl, TypeAdapter

from book_store_assistant.enrichment.page_fetch import extract_description_candidates_from_html
from book_store_assistant.isbn import normalize_isbn
from book_store_assistant.resolution.synopsis_resolution import is_spanish_language
from book_store_assistant.sources.cache import FetchResultCache
from book_store_assistant.sources.issues import classify_http_issue, no_match_issue_code
from book_store_assistant.sources.language_codes import normalize_language_code
from book_store_assistant.sources.merge import merge_source_records
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult

BOOKISH_TYPES = {"book", "product", "creativework"}
DUCKDUCKGO_HTML_SEARCH_URL = "https://html.duckduckgo.com/html/"
RESULT_LINK_PATTERN = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"',
    re.IGNORECASE,
)
OG_TITLE_PATTERN = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL,
)
OG_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL,
)
TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
HTML_LANG_PATTERN = re.compile(r"<html[^>]+lang=[\"']([^\"']+)[\"']", re.IGNORECASE)
JSON_LD_SCRIPT_PATTERN = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
ISBN_PATTERN = re.compile(r"\b97[89][\d\-\s]{10,17}\b|\b[\d\-\s]{9,16}[Xx]\b")
EDITORIAL_LABEL_PATTERN = re.compile(
    r"(?:editorial|publisher)\s*[:|]\s*([^\n|]+)",
    re.IGNORECASE,
)
HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)
PublisherPageStatusCallback = Callable[[str], None]
PUBLISHER_PAGE_CACHE_KEY = "publisher_page_lookup_v1"
PUBLISHER_PAGE_ISBN_MISMATCH = "PUBLISHER_PAGE_ISBN_MISMATCH"


@dataclass(frozen=True)
class PublisherProfile:
    key: str
    domains: tuple[str, ...]
    editorial_aliases: tuple[str, ...]


SUPPORTED_PUBLISHERS = (
    PublisherProfile(
        key="penguin_random_house",
        domains=("penguinlibros.com", "megustaleer.com"),
        editorial_aliases=(
            "penguin random house",
            "penguin random house grupo editorial",
            "penguin libros",
            "alfaguara",
            "aguilar",
            "debolsillo",
            "grijalbo",
            "lumen",
            "montena",
            "beascoa",
            "molino",
            "plaza janes",
            "plaza & janes",
            "de borsillo",
            "random comics",
            "reservoir books",
            "roca editorial",
            "salamandra",
            "suma",
            "taurus",
            "nube de tinta",
            "caballo de troya",
            "conecta",
            "electa",
            "futuropolis",
            "penguin clasicos",
            "real academia espanola",
            "real academia española",
        ),
    ),
    PublisherProfile(
        key="planeta",
        domains=("planetadelibros.com",),
        editorial_aliases=(
            "planeta",
            "editorial planeta",
            "planeta de libros",
            "booket",
            "destino",
            "espasa",
            "seix barral",
            "ariel",
            "paidos",
            "paidos",
            "tusquets",
            "austral",
            "alienta",
            "alienta editorial",
            "booket",
            "critica",
            "crítica",
            "cupula",
            "cúpula",
            "deusto",
            "destino infantil juvenil",
            "ediciones peninsula",
            "galera",
            "geo planeta",
            "grupo planeta",
            "grupo planeta gbs",
            "grupo planeta spain",
            "libros cupula",
            "libros cúpula",
            "peninsula",
            "península",
            "temas de hoy",
        ),
    ),
    PublisherProfile(
        key="anagrama",
        domains=("anagrama-ed.es",),
        editorial_aliases=(
            "anagrama",
            "editorial anagrama",
        ),
    ),
    PublisherProfile(
        key="urano",
        domains=("edicionesurano.com",),
        editorial_aliases=(
            "urano",
            "ediciones urano",
            "empresa activa",
            "entramat",
            "indicios",
            "kepler",
            "kitsune books",
            "luciernaga",
            "puck",
            "titania",
            "umbriel",
            "uranito",
        ),
    ),
    PublisherProfile(
        key="galaxia_gutenberg",
        domains=("galaxiagutenberg.com",),
        editorial_aliases=(
            "galaxia gutenberg",
            "circulo de lectores",
            "círculo de lectores",
        ),
    ),
    PublisherProfile(
        key="norma_editorial",
        domains=("normaeditorial.com",),
        editorial_aliases=(
            "norma editorial",
            "norma s a editorial",
            "editorial norma",
        ),
    ),
    PublisherProfile(
        key="lectorum",
        domains=("lectorum.com",),
        editorial_aliases=(
            "lectorum",
            "lectorum publications",
        ),
    ),
)


class PublisherPageSearcher:
    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = 3,
    ) -> list[str]:
        raise NotImplementedError


class PageContentFetcher:
    def fetch_text(self, url: str) -> str | None:
        raise NotImplementedError


class DuckDuckGoHtmlSearcher(PublisherPageSearcher):
    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = 3,
    ) -> list[str]:
        domain_query = " OR ".join(f"site:{domain}" for domain in allowed_domains)
        full_query = f"{query} ({domain_query})" if domain_query else query

        try:
            response = httpx.get(
                DUCKDUCKGO_HTML_SEARCH_URL,
                params={"q": full_query},
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise

        links: list[str] = []
        seen: set[str] = set()

        for match in RESULT_LINK_PATTERN.finditer(response.text):
            link = _decode_search_result_link(unescape(match.group(1)))
            if link is None or not _is_allowed_domain(link, allowed_domains):
                continue

            if link in seen:
                continue

            seen.add(link)
            links.append(link)
            if len(links) >= limit:
                break

        return links


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    stripped = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    compact = re.sub(r"[^a-z0-9]+", " ", stripped.casefold()).strip()
    return " ".join(compact.split())


def _clean_text(value: str) -> str:
    normalized = re.sub(r"<[^>]+>", " ", value)
    normalized = re.sub(r"\s+", " ", unescape(normalized)).strip()
    return normalized


def _seed_field_sources(record: SourceBookRecord) -> dict[str, str]:
    field_sources = dict(record.field_sources)

    for field_name in (
        "title",
        "subtitle",
        "author",
        "editorial",
        "synopsis",
        "subject",
        "language",
    ):
        if getattr(record, field_name) and field_name not in field_sources:
            field_sources[field_name] = record.source_name

    if record.cover_url is not None and "cover_url" not in field_sources:
        field_sources["cover_url"] = record.source_name

    if record.source_url is not None and "source_url" not in field_sources:
        field_sources["source_url"] = record.source_name

    if record.categories and "categories" not in field_sources:
        field_sources["categories"] = record.source_name

    return field_sources


def _decode_search_result_link(value: str) -> str | None:
    if value.startswith("//"):
        return f"https:{value}"

    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        query = parse_qs(parsed.query)
        redirected = query.get("uddg")
        if redirected:
            return unquote(redirected[0])
        return value

    return None


def _is_allowed_domain(url: str, allowed_domains: tuple[str, ...]) -> bool:
    hostname = urlparse(url).hostname
    if hostname is None:
        return False

    normalized_hostname = hostname.casefold()
    return any(
        normalized_hostname == domain or normalized_hostname.endswith(f".{domain}")
        for domain in allowed_domains
    )


def _looks_like_supported_bookish_item(payload: dict) -> bool:
    raw_type = payload.get("@type")
    if isinstance(raw_type, str):
        return raw_type.casefold() in BOOKISH_TYPES

    if isinstance(raw_type, list):
        return any(isinstance(item, str) and item.casefold() in BOOKISH_TYPES for item in raw_type)

    return False


def _extract_string(value: object) -> str | None:
    if isinstance(value, str):
        cleaned = _clean_text(value)
        return cleaned or None

    if isinstance(value, dict):
        for key in ("name", "value", "@value"):
            nested = value.get(key)
            if isinstance(nested, str):
                cleaned = _clean_text(nested)
                return cleaned or None

    return None


def _extract_person_names(value: object) -> str | None:
    if isinstance(value, str):
        cleaned = _clean_text(value)
        return cleaned or None

    if isinstance(value, dict):
        return _extract_string(value)

    if isinstance(value, list):
        names = [name for item in value if (name := _extract_person_names(item)) is not None]
        if names:
            return ", ".join(names)

    return None


def _extract_image_url(value: object) -> str | None:
    if isinstance(value, str):
        return value

    if isinstance(value, list):
        for item in value:
            image_url = _extract_image_url(item)
            if image_url is not None:
                return image_url

    if isinstance(value, dict):
        for key in ("url", "contentUrl"):
            nested = value.get(key)
            if isinstance(nested, str):
                return nested

    return None


def _extract_json_ld_book_payloads(payload: object) -> list[dict]:
    if isinstance(payload, list):
        list_collected: list[dict] = []
        for item in payload:
            list_collected.extend(_extract_json_ld_book_payloads(item))
        return list_collected

    if not isinstance(payload, dict):
        return []

    collected: list[dict] = []
    if _looks_like_supported_bookish_item(payload):
        collected.append(payload)

    graph = payload.get("@graph")
    if graph is not None:
        collected.extend(_extract_json_ld_book_payloads(graph))

    for value in payload.values():
        if isinstance(value, (dict, list)):
            collected.extend(_extract_json_ld_book_payloads(value))

    return collected


def _coerce_http_url(value: str | None) -> HttpUrl | None:
    if value is None:
        return None

    try:
        return HTTP_URL_ADAPTER.validate_python(value)
    except Exception:
        return None


def _extract_json_ld_record(html: str, isbn: str) -> SourceBookRecord | None:
    normalized_isbn = normalize_isbn(isbn)
    candidates: list[SourceBookRecord] = []

    for match in JSON_LD_SCRIPT_PATTERN.finditer(html):
        script_text = match.group(1).strip()
        if not script_text:
            continue

        try:
            payload = json.loads(unescape(script_text))
        except json.JSONDecodeError:
            continue

        for bookish in _extract_json_ld_book_payloads(payload):
            raw_isbn_values = [
                bookish.get("isbn"),
                bookish.get("isbn13"),
                bookish.get("productID"),
                bookish.get("gtin13"),
            ]
            extracted_isbn_values = [
                normalize_isbn(candidate)
                for raw_value in raw_isbn_values
                for candidate in (
                    [raw_value]
                    if isinstance(raw_value, str)
                    else raw_value
                    if isinstance(raw_value, list)
                    else []
                )
                if normalize_isbn(candidate)
            ]
            if extracted_isbn_values and normalized_isbn not in extracted_isbn_values:
                continue

            candidates.append(
                SourceBookRecord(
                    source_name="publisher_page",
                    isbn=isbn,
                    title=_extract_string(bookish.get("name")),
                    subtitle=_extract_string(bookish.get("alternateName")),
                    author=_extract_person_names(bookish.get("author")),
                    editorial=_extract_person_names(bookish.get("publisher")),
                    synopsis=_extract_string(bookish.get("description")),
                    cover_url=_coerce_http_url(_extract_image_url(bookish.get("image"))),
                )
            )

    if not candidates:
        return None

    return merge_source_records(candidates)


def match_publisher_profile(editorial: str | None) -> PublisherProfile | None:
    if editorial is None:
        return None

    normalized_editorial = _normalize_text(editorial)
    if not normalized_editorial:
        return None

    raw_candidates = [
        editorial,
        *(
            candidate.strip()
            for candidate in re.split(r"[,/;|&()\[\]]+", editorial)
            if candidate.strip()
        ),
    ]
    candidates = {
        normalized_candidate
        for candidate in raw_candidates
        if (normalized_candidate := _normalize_text(candidate))
    }

    for profile in SUPPORTED_PUBLISHERS:
        aliases = {
            _normalize_text(profile.key),
            *(_normalize_text(alias) for alias in profile.editorial_aliases),
        }
        if candidates & aliases:
            return profile

    return None


def build_publisher_search_query(record: SourceBookRecord) -> str:
    query_parts = [f'"{record.isbn}"']

    if record.title:
        query_parts.append(f'"{record.title}"')
        title_head = record.title.split(":", maxsplit=1)[0].strip()
        if title_head and title_head != record.title:
            query_parts.append(f'"{title_head}"')

    if record.author:
        primary_author = record.author.split(",", maxsplit=1)[0].strip()
        if primary_author:
            query_parts.append(f'"{primary_author}"')

    if record.editorial:
        query_parts.append(f'"{record.editorial}"')

    return " ".join(query_parts)


def _score_candidate_url(url: str, record: SourceBookRecord) -> tuple[int, int, int]:
    normalized_url = _normalize_text(url)
    title_score = 0
    author_score = 0
    isbn_score = 1 if record.isbn in url else 0

    if record.title:
        title_head = record.title.split(":", maxsplit=1)[0].strip()
        normalized_title = _normalize_text(title_head or record.title)
        if normalized_title and normalized_title in normalized_url:
            title_score = 2
        elif normalized_title:
            title_tokens = [token for token in normalized_title.split() if len(token) > 3]
            title_score = 1 if title_tokens and all(token in normalized_url for token in title_tokens[:3]) else 0

    if record.author:
        primary_author = record.author.split(",", maxsplit=1)[0].strip()
        normalized_author = _normalize_text(primary_author)
        author_tokens = [token for token in normalized_author.split() if len(token) > 2]
        if author_tokens and any(token in normalized_url for token in author_tokens):
            author_score = 1

    return (isbn_score, title_score, author_score)


def _rank_candidate_urls(candidate_urls: list[str], record: SourceBookRecord) -> list[str]:
    return sorted(
        candidate_urls,
        key=lambda candidate_url: _score_candidate_url(candidate_url, record),
        reverse=True,
    )


def _extract_html_title(html: str) -> str | None:
    for pattern in (OG_TITLE_PATTERN, TITLE_PATTERN):
        match = pattern.search(html)
        if match is not None:
            cleaned = _clean_text(match.group(1))
            if cleaned:
                return cleaned

    return None


def _extract_html_language(html: str) -> str | None:
    match = HTML_LANG_PATTERN.search(html)
    if match is None:
        return None

    return normalize_language_code(match.group(1))


def _extract_editorial_from_text(html: str) -> str | None:
    text = _clean_text(html)
    match = EDITORIAL_LABEL_PATTERN.search(text)
    if match is None:
        return None

    editorial = match.group(1).strip(" .|")
    return editorial or None


def _extract_isbn_candidates(html: str) -> set[str]:
    return {
        normalize_isbn(match.group(0))
        for match in ISBN_PATTERN.finditer(_clean_text(html))
        if normalize_isbn(match.group(0))
    }


def extract_publisher_page_record(
    html: str,
    page_url: str,
    isbn: str,
    profile: PublisherProfile,
) -> SourceBookRecord | None:
    isbn_candidates = _extract_isbn_candidates(html)
    normalized_isbn = normalize_isbn(isbn)
    if normalized_isbn not in isbn_candidates:
        return None

    json_ld_record = _extract_json_ld_record(html, isbn)
    descriptions = extract_description_candidates_from_html(html, source_url=page_url)
    synopsis = descriptions[0][1] if descriptions else None

    if json_ld_record is not None:
        field_sources = _seed_field_sources(json_ld_record)
        return json_ld_record.model_copy(
            update={
                "source_name": f"publisher_page:{profile.key}",
                "isbn": isbn,
                "source_url": _coerce_http_url(page_url),
                "synopsis": json_ld_record.synopsis or synopsis,
                "editorial": json_ld_record.editorial or _extract_editorial_from_text(html),
                "language": _extract_html_language(html),
                "field_sources": field_sources,
            }
        )

    title = _extract_html_title(html)
    cover_url_match = OG_IMAGE_PATTERN.search(html)
    cover_url = cover_url_match.group(1).strip() if cover_url_match is not None else None

    if title is None and synopsis is None:
        return None

    return SourceBookRecord(
        source_name=f"publisher_page:{profile.key}",
        isbn=isbn,
        source_url=_coerce_http_url(page_url),
        title=title,
        editorial=_extract_editorial_from_text(html),
        synopsis=synopsis,
        cover_url=_coerce_http_url(cover_url),
        language=_extract_html_language(html),
    )


def _should_replace_synopsis(
    existing_record: SourceBookRecord,
    publisher_record: SourceBookRecord,
) -> bool:
    if publisher_record.synopsis is None:
        return False

    if existing_record.synopsis is None:
        return True

    if existing_record.language == "es":
        return False

    return publisher_record.language == "es"


def _merge_categories(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for value in [*primary, *secondary]:
        normalized = value.strip()
        if not normalized:
            continue

        key = normalized.casefold()
        if key in seen:
            continue

        seen.add(key)
        merged.append(normalized)

    return merged


def _merge_issue_codes(*values: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for items in values:
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)

    return merged


def apply_publisher_page_record(
    existing_record: SourceBookRecord,
    publisher_record: SourceBookRecord,
) -> SourceBookRecord:
    merged_record = merge_source_records([existing_record, publisher_record])
    field_sources = _seed_field_sources(merged_record)

    updates: dict[str, object] = {
        "categories": _merge_categories(existing_record.categories, publisher_record.categories),
        "field_sources": field_sources,
    }

    if publisher_record.source_url is not None:
        field_sources["source_url"] = publisher_record.source_name
        updates["source_url"] = publisher_record.source_url

    if _should_replace_synopsis(existing_record, publisher_record):
        field_sources["synopsis"] = publisher_record.source_name
        updates["synopsis"] = publisher_record.synopsis
        updates["language"] = publisher_record.language or "es"
        field_sources["language"] = publisher_record.source_name

    return merged_record.model_copy(update=updates)


def _needs_publisher_discovery(record: SourceBookRecord) -> bool:
    return not record.editorial


def _needs_publisher_lookup(record: SourceBookRecord) -> bool:
    synopsis_needs_support = (
        not record.synopsis
        or record.language is None
        or not is_spanish_language(record.language)
    )
    return not (
        record.title
        and record.author
        and record.editorial
        and (record.subject or record.categories)
        and not synopsis_needs_support
    )


def _candidate_publisher_profiles(record: SourceBookRecord) -> list[PublisherProfile]:
    matched_profile = match_publisher_profile(record.editorial)
    if not _needs_publisher_discovery(record):
        return [matched_profile] if matched_profile is not None else []

    candidate_profiles: list[PublisherProfile] = []
    seen_profile_keys: set[str] = set()

    if matched_profile is not None:
        candidate_profiles.append(matched_profile)
        seen_profile_keys.add(matched_profile.key)

    for profile in SUPPORTED_PUBLISHERS:
        if profile.key in seen_profile_keys:
            continue
        seen_profile_keys.add(profile.key)
        candidate_profiles.append(profile)

    return candidate_profiles


def augment_fetch_results_with_publisher_pages(
    fetch_results: list[FetchResult],
    timeout_seconds: float,
    searcher: PublisherPageSearcher | None = None,
    page_fetcher: PageContentFetcher | None = None,
    on_status_update: PublisherPageStatusCallback | None = None,
    cache: FetchResultCache | None = None,
) -> list[FetchResult]:
    active_searcher = searcher or DuckDuckGoHtmlSearcher(timeout_seconds)
    active_page_fetcher = page_fetcher or _DefaultPageFetcher(timeout_seconds)
    augmented_results: list[FetchResult] = []

    if on_status_update is not None:
        on_status_update(
            f"Stage: checking publisher pages for {len(fetch_results)} fetched records"
        )

    for index, fetch_result in enumerate(fetch_results, start=1):
        record = fetch_result.record
        if record is None:
            augmented_results.append(fetch_result)
            continue

        if not _needs_publisher_lookup(record):
            augmented_results.append(fetch_result)
            continue

        cached_result = cache.get(record.isbn) if cache is not None else None
        if cached_result is not None and cached_result.record is not None:
            augmented_results.append(
                fetch_result.model_copy(
                    update={"record": apply_publisher_page_record(record, cached_result.record)}
                )
            )
            continue

        candidate_profiles = _candidate_publisher_profiles(record)
        if not candidate_profiles:
            augmented_results.append(fetch_result)
            continue

        page_url: str | None = None
        publisher_issue_codes: list[str] = []
        query = build_publisher_search_query(record)
        if on_status_update is not None:
            on_status_update(
                f"Publisher lookup {index}/{len(fetch_results)}: {record.isbn}"
            )
        for profile in candidate_profiles:
            try:
                candidate_urls = active_searcher.search(query, profile.domains)
            except httpx.HTTPError as exc:
                publisher_issue_codes = _merge_issue_codes(
                    publisher_issue_codes,
                    classify_http_issue("publisher_page_search", exc),
                )
                continue

            for candidate_url in _rank_candidate_urls(candidate_urls, record):
                if not _is_allowed_domain(candidate_url, profile.domains):
                    continue

                try:
                    page_html = active_page_fetcher.fetch_text(candidate_url)
                except httpx.HTTPError as exc:
                    publisher_issue_codes = _merge_issue_codes(
                        publisher_issue_codes,
                        classify_http_issue("publisher_page_fetch", exc),
                    )
                    continue

                if page_html is None:
                    continue

                if normalize_isbn(record.isbn) not in _extract_isbn_candidates(page_html):
                    publisher_issue_codes = _merge_issue_codes(
                        publisher_issue_codes,
                        [PUBLISHER_PAGE_ISBN_MISMATCH],
                    )
                    continue

                publisher_record = extract_publisher_page_record(
                    page_html,
                    candidate_url,
                    record.isbn,
                    profile,
                )
                if publisher_record is None:
                    continue

                page_url = candidate_url
                if cache is not None:
                    cache.set(
                        FetchResult(
                            isbn=record.isbn,
                            record=publisher_record,
                            errors=[],
                            issue_codes=[],
                        )
                    )
                augmented_results.append(
                    fetch_result.model_copy(
                        update={"record": apply_publisher_page_record(record, publisher_record)}
                    )
                )
                break

            if page_url is not None:
                break

        if page_url is None:
            augmented_results.append(
                fetch_result.model_copy(
                    update={
                        "issue_codes": _merge_issue_codes(
                            fetch_result.issue_codes,
                            publisher_issue_codes,
                            [no_match_issue_code("publisher_page")],
                        )
                    }
                )
            )

    return augmented_results


class _DefaultPageFetcher:
    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_text(self, url: str) -> str | None:
        try:
            response = httpx.get(
                url,
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise

        return response.text
