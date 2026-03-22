import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from html import unescape
from urllib.parse import quote

import httpx

from book_store_assistant.isbn import normalize_isbn
from book_store_assistant.sources.exact_page_lookup import lookup_exact_page_record
from book_store_assistant.sources.issues import no_match_issue_code
from book_store_assistant.sources.merge import merge_source_records
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.publisher_pages import (
    SEARCH_RESULT_LIMIT,
    DuckDuckGoHtmlSearcher,
    PageContentFetcher,
    PublisherPageSearcher,
    _clean_text,
    _coerce_http_url,
    _extract_html_title,
    _extract_isbn_candidates,
    _extract_json_ld_record,
    _is_allowed_domain,
    _rank_candidate_urls,
    _run_with_retry,
)
from book_store_assistant.sources.results import FetchResult

RetailerStatusCallback = Callable[[str], None]

AUTHOR_LABEL_PATTERN = re.compile(
    r"(?:autor(?:es)?|author)\s*[:|]\s*([^\n|]+)",
    re.IGNORECASE,
)
EDITORIAL_LABEL_PATTERN = re.compile(
    r"(?:editorial|editor|publisher|sello)\s*[:|]\s*([^\n|]+)",
    re.IGNORECASE,
)
META_DESCRIPTION_PATTERN = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL,
)
AGAPEA_EDITORIAL_PATTERN = re.compile(
    r"comprar el libro .*? de .*?,\s*([^()]+?)\s*\((?:97[89]\d{10})\)",
    re.IGNORECASE,
)
AGAPEA_AUTHOR_PATTERN = re.compile(
    r"comprar el libro .*? de (.*?),\s*[^()]+?\s*\((?:97[89]\d{10})\)",
    re.IGNORECASE,
)
INLINE_EDITORIAL_PATTERN = re.compile(
    r"(?:editorial|publisher)\s+(.+?)(?:\.\s+[A-ZÁÉÍÓÚÜÑ]|,\s*\d{4}|\s*$)",
    re.IGNORECASE,
)
INLINE_AUTHOR_PATTERN = re.compile(
    r"(?:autor(?:es)?|author)\s+(.+?)(?:\.\s+[A-ZÁÉÍÓÚÜÑ]|,\s*(?:editorial|publisher)|\s*$)",
    re.IGNORECASE,
)
SUBJECT_LABEL_PATTERN = re.compile(
    r"(?:tem[aá]ticas?|tem[aá]tica|materia(?:s)?|categor[ií]as?|g[eé]nero)\s*[:|]\s*([^\n|]+)",
    re.IGNORECASE,
)
JSON_SCRIPT_PATTERN = re.compile(
    r"<script[^>]*>\s*(\{.*?\}|\[.*?\])\s*</script>",
    re.IGNORECASE | re.DOTALL,
)
GARBAGE_METADATA_TOKENS = (
    '{"id"',
    '"nombreweb"',
    '"seoprice"',
    '"seocurrentprice"',
    "top más leídos",
    "promociones",
    "comprar libros",
)


@dataclass(frozen=True)
class RetailerProfile:
    key: str
    domains: tuple[str, ...]
    direct_query_urls: tuple[str, ...] = ()


SUPPORTED_RETAILERS = (
    RetailerProfile(
        key="agapea",
        domains=("agapea.com",),
        direct_query_urls=("https://www.agapea.com/buscador/buscador.php?texto={isbn}",),
    ),
    RetailerProfile(
        key="buscalibre",
        domains=(
            "buscalibre.com",
            "buscalibre.cl",
            "buscalibre.com.co",
            "buscalibre.com.mx",
            "buscalibre.pe",
            "buscalibre.us",
        ),
    ),
    RetailerProfile(
        key="casa_del_libro",
        domains=("casadellibro.com", "casadellibro.com.co"),
        direct_query_urls=(
            "https://www.casadellibro.com.co/?query={isbn}",
            "https://www.casadellibro.com/?query={isbn}",
        ),
    ),
    RetailerProfile(
        key="libreria_nacional",
        domains=("librerianacional.com",),
    ),
    RetailerProfile(
        key="fnac",
        domains=("fnac.es",),
    ),
    RetailerProfile(
        key="panamericana",
        domains=("panamericana.com.co",),
    ),
    RetailerProfile(
        key="todostuslibros",
        domains=("todostuslibros.com",),
    ),
)


def _extract_labeled_value(html: str, pattern: re.Pattern[str]) -> str | None:
    text = _clean_text(html)
    match = pattern.search(text)
    if match is None:
        return None
    value = match.group(1).strip(" .|")
    return value or None


def _extract_meta_description(html: str) -> str | None:
    match = META_DESCRIPTION_PATTERN.search(html)
    if match is None:
        return None
    description = _clean_text(unescape(match.group(1)))
    return description or None


def _extract_agapea_editorial(html: str, isbn: str) -> str | None:
    description = _extract_meta_description(html)
    if description is None or isbn not in description:
        return None

    match = AGAPEA_EDITORIAL_PATTERN.search(description)
    if match is None:
        return None

    editorial = " ".join(unescape(match.group(1)).split()).strip(" ,.")
    return editorial or None


def _extract_agapea_author(html: str, isbn: str) -> str | None:
    description = _extract_meta_description(html)
    if description is None or isbn not in description:
        return None

    match = AGAPEA_AUTHOR_PATTERN.search(description)
    if match is None:
        return None

    author = " ".join(unescape(match.group(1)).split()).strip(" ,.")
    return author or None


def _extract_inline_editorial(html: str) -> str | None:
    text = _clean_text(html)
    match = INLINE_EDITORIAL_PATTERN.search(text)
    if match is None:
        return None

    editorial = match.group(1).strip(" .|")
    return editorial or None


def _extract_inline_author(html: str) -> str | None:
    text = _clean_text(html)
    match = INLINE_AUTHOR_PATTERN.search(text)
    if match is None:
        return None

    author = match.group(1).strip(" .|")
    return author or None


def _clean_retailer_metadata_value(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = _clean_text(value)
    if not cleaned:
        return None
    lowered = cleaned.casefold()
    if any(token in lowered for token in GARBAGE_METADATA_TOKENS):
        return None
    if "{" in cleaned or "}" in cleaned:
        return None
    if len(cleaned) > 180:
        return None
    return cleaned


def _split_category_text(value: str) -> list[str]:
    parts = re.split(r"[|;,>/]+", value)
    return [part.strip() for part in parts if part.strip()]


def _clean_retailer_categories(values: list[str]) -> list[str]:
    cleaned_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = _clean_retailer_metadata_value(value)
        if cleaned is None:
            continue

        key = cleaned.casefold()
        if key in seen:
            continue

        seen.add(key)
        cleaned_values.append(cleaned)

    return cleaned_values


def _extract_subject_candidates_from_text(html: str) -> list[str]:
    text = _clean_text(html)
    match = SUBJECT_LABEL_PATTERN.search(text)
    if match is None:
        return []

    return _clean_retailer_categories(_split_category_text(match.group(1)))


def _extract_json_objects(html: str) -> list[object]:
    payloads: list[object] = []

    for match in JSON_SCRIPT_PATTERN.finditer(html):
        script_text = match.group(1).strip()
        if not script_text:
            continue

        try:
            payloads.append(json.loads(unescape(script_text)))
        except json.JSONDecodeError:
            continue

    return payloads


def _collect_matching_json_records(payload: object, normalized_isbn: str) -> list[dict]:
    if isinstance(payload, list):
        nested_matches: list[dict] = []
        for item in payload:
            nested_matches.extend(_collect_matching_json_records(item, normalized_isbn))
        return nested_matches

    if not isinstance(payload, dict):
        return []

    matches: list[dict] = []
    raw_candidates = [payload.get("isbn"), payload.get("isbn13"), payload.get("ean")]
    normalized_candidates = {
        normalize_isbn(candidate)
        for raw_value in raw_candidates
        for candidate in (
            [raw_value]
            if isinstance(raw_value, str)
            else raw_value
            if isinstance(raw_value, list)
            else []
        )
        if isinstance(candidate, str) and normalize_isbn(candidate)
    }
    if normalized_isbn in normalized_candidates:
        matches.append(payload)

    for value in payload.values():
        if isinstance(value, (dict, list)):
            matches.extend(_collect_matching_json_records(value, normalized_isbn))

    return matches


def _extract_author_from_json_payload(html: str, isbn: str) -> str | None:
    normalized_isbn = normalize_isbn(isbn)
    for payload in _extract_json_objects(html):
        for record in _collect_matching_json_records(payload, normalized_isbn):
            authors = record.get("authors")
            if isinstance(authors, list):
                names: list[str] = []
                for item in authors:
                    if isinstance(item, dict):
                        name = item.get("name")
                        if isinstance(name, str) and name.strip():
                            names.append(_clean_text(name))
                    elif isinstance(item, str) and item.strip():
                        names.append(_clean_text(item))
                if names:
                    return ", ".join(names)

            author = record.get("author")
            if isinstance(author, str) and author.strip():
                return _clean_text(author)

    return None


def _extract_category_values(value: object) -> list[str]:
    if isinstance(value, str):
        return _clean_retailer_categories(_split_category_text(_clean_text(value)))

    if isinstance(value, dict):
        for key in ("name", "value", "@value"):
            nested = value.get(key)
            if isinstance(nested, str):
                return _clean_retailer_categories(_split_category_text(_clean_text(nested)))
        return []

    if isinstance(value, list):
        collected: list[str] = []
        for item in value:
            collected.extend(_extract_category_values(item))
        return _clean_retailer_categories(collected)

    return []


def _extract_categories_from_json_payload(html: str, isbn: str) -> list[str]:
    normalized_isbn = normalize_isbn(isbn)
    for payload in _extract_json_objects(html):
        for record in _collect_matching_json_records(payload, normalized_isbn):
            categories = _clean_retailer_categories(
                [
                    *_extract_category_values(record.get("genre")),
                    *_extract_category_values(record.get("keywords")),
                    *_extract_category_values(record.get("about")),
                ]
            )
            if categories:
                return categories

    return []


def _extract_editorial_from_json_payload(html: str, isbn: str) -> str | None:
    normalized_isbn = normalize_isbn(isbn)
    for payload in _extract_json_objects(html):
        for record in _collect_matching_json_records(payload, normalized_isbn):
            editorial = record.get("editorial")
            if isinstance(editorial, str) and editorial.strip():
                cleaned = _clean_text(editorial)
                if cleaned and len(cleaned) <= 120 and "{" not in cleaned:
                    return cleaned

            publisher = record.get("publisher")
            if isinstance(publisher, dict):
                name = publisher.get("name")
                if isinstance(name, str) and name.strip():
                    return _clean_text(name)
            if isinstance(publisher, str) and publisher.strip():
                return _clean_text(publisher)

    return None


def _sanitize_retailer_record(record: SourceBookRecord) -> SourceBookRecord | None:
    title = _clean_retailer_metadata_value(record.title)
    author = _clean_retailer_metadata_value(record.author)
    editorial = _clean_retailer_metadata_value(record.editorial)
    categories = _clean_retailer_categories(record.categories)

    if editorial is None and author is None and not categories:
        return None

    return record.model_copy(
        update={
            "title": title,
            "author": author,
            "editorial": editorial,
            "categories": categories,
        }
    )


def _build_direct_query_urls(record: SourceBookRecord, profile: RetailerProfile) -> list[str]:
    encoded_isbn = quote(record.isbn, safe="")
    return [template.format(isbn=encoded_isbn) for template in profile.direct_query_urls]


def _retailer_lookup_issue_code(code: str) -> str:
    if code == "PAGE_SEARCH_BUDGET_EXHAUSTED":
        return "RETAILER_PAGE_SEARCH_BUDGET_EXHAUSTED"
    if code == "PAGE_FETCH_BUDGET_EXHAUSTED":
        return "RETAILER_PAGE_FETCH_BUDGET_EXHAUSTED"
    return code


def extract_retailer_page_record(
    html: str,
    page_url: str,
    isbn: str,
    profile: RetailerProfile,
) -> SourceBookRecord | None:
    if isbn not in _extract_isbn_candidates(html):
        return None

    json_ld_record = _extract_json_ld_record(html, isbn)
    text_categories = _extract_subject_candidates_from_text(html)
    json_categories = _extract_categories_from_json_payload(html, isbn)
    categories = _clean_retailer_categories([*json_categories, *text_categories])
    if json_ld_record is not None and (json_ld_record.editorial or json_ld_record.author):
        return SourceBookRecord(
            source_name=f"retailer_page:{profile.key}",
            isbn=isbn,
            source_url=_coerce_http_url(page_url),
            title=json_ld_record.title,
            author=json_ld_record.author,
            editorial=json_ld_record.editorial,
            synopsis=json_ld_record.synopsis,
            categories=_clean_retailer_categories([*json_ld_record.categories, *categories]),
            cover_url=json_ld_record.cover_url,
        )

    title = _extract_html_title(html)
    author = (
        _extract_labeled_value(html, AUTHOR_LABEL_PATTERN)
        or _extract_agapea_author(html, isbn)
        or _extract_author_from_json_payload(html, isbn)
        or _extract_inline_author(html)
    )
    editorial = (
        _extract_editorial_from_json_payload(html, isbn)
        or _extract_labeled_value(html, EDITORIAL_LABEL_PATTERN)
        or _extract_agapea_editorial(html, isbn)
        or _extract_inline_editorial(html)
    )
    title = _clean_retailer_metadata_value(title)
    author = _clean_retailer_metadata_value(author)
    editorial = _clean_retailer_metadata_value(editorial)
    if editorial is None and author is None:
        return None

    return SourceBookRecord(
        source_name=f"retailer_page:{profile.key}",
        isbn=isbn,
        source_url=_coerce_http_url(page_url),
        title=title,
        author=author,
        editorial=editorial,
        categories=categories,
    )


def _needs_retailer_metadata_lookup(record: SourceBookRecord) -> bool:
    return not record.title or not record.editorial or not record.author


def build_retailer_search_query(record: SourceBookRecord) -> str:
    return f'"{record.isbn}"'


def build_retailer_search_queries(record: SourceBookRecord) -> list[str]:
    return [build_retailer_search_query(record)]


def apply_retailer_editorial_record(
    existing_record: SourceBookRecord,
    retailer_record: SourceBookRecord,
) -> SourceBookRecord:
    merged_record = merge_source_records([existing_record, retailer_record])
    field_sources = dict(merged_record.field_sources)
    field_confidence = dict(merged_record.field_confidence)

    if not existing_record.editorial and retailer_record.editorial:
        field_sources["editorial"] = retailer_record.source_name
        field_confidence["editorial"] = 0.55
    if not existing_record.author and retailer_record.author:
        field_sources["author"] = retailer_record.source_name
        field_confidence["author"] = 0.55
    if not existing_record.synopsis and retailer_record.synopsis:
        field_sources["synopsis"] = retailer_record.source_name
        field_confidence["synopsis"] = 0.45

    return merged_record.model_copy(
        update={
            "field_sources": field_sources,
            "field_confidence": field_confidence,
        }
    )


def augment_fetch_results_with_retailer_editorials(
    fetch_results: list[FetchResult],
    timeout_seconds: float,
    searcher: PublisherPageSearcher | None = None,
    page_fetcher: PageContentFetcher | None = None,
    on_status_update: RetailerStatusCallback | None = None,
    max_retries: int = 2,
    backoff_seconds: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
    max_search_attempts_per_record: int | None = None,
    max_fetch_attempts_per_record: int | None = None,
) -> list[FetchResult]:
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        active_searcher = searcher or DuckDuckGoHtmlSearcher(timeout_seconds, client=client)
        active_page_fetcher = page_fetcher or _DefaultRetailerPageFetcher(
            timeout_seconds,
            client=client,
        )
        augmented_results: list[FetchResult] = []

        if on_status_update is not None:
            on_status_update(
                f"Stage: checking retailer pages for {len(fetch_results)} fetched records"
            )

        for index, fetch_result in enumerate(fetch_results, start=1):
            record = fetch_result.record
            if record is None or not _needs_retailer_metadata_lookup(record):
                augmented_results.append(fetch_result)
                continue

            if on_status_update is not None:
                on_status_update(
                    f"Retailer editorial lookup {index}/{len(fetch_results)}: {record.isbn}"
                )

            retailer_record, raw_issue_codes = lookup_exact_page_record(
                record,
                SUPPORTED_RETAILERS,
                search_queries=lambda current_record, _profile: build_retailer_search_queries(
                    current_record
                ),
                direct_query_urls=_build_direct_query_urls,
                extract_record=extract_retailer_page_record,
                search=active_searcher.search,
                fetch_text=active_page_fetcher.fetch_text,
                run_with_retry=_run_with_retry,
                rank_candidate_urls=_rank_candidate_urls,
                is_allowed_domain=_is_allowed_domain,
                search_issue_source="retailer_page_search",
                fetch_issue_source="retailer_page_fetch",
                search_result_limit=SEARCH_RESULT_LIMIT,
                max_retries=max_retries,
                backoff_seconds=backoff_seconds,
                sleep=sleep,
                max_search_attempts_per_record=max_search_attempts_per_record,
                max_fetch_attempts_per_record=max_fetch_attempts_per_record,
            )
            retailer_issue_codes = [
                _retailer_lookup_issue_code(code)
                for code in raw_issue_codes
            ]
            retailer_record = (
                _sanitize_retailer_record(retailer_record)
                if retailer_record is not None
                else None
            )

            if retailer_record is None:
                failed_result = fetch_result.model_copy(
                    update={
                        "issue_codes": [
                            *fetch_result.issue_codes,
                            *(
                                code
                                for code in retailer_issue_codes
                                if code not in fetch_result.issue_codes
                            ),
                            *(
                                [no_match_issue_code("retailer_page_editorial")]
                                if no_match_issue_code("retailer_page_editorial")
                                not in fetch_result.issue_codes
                                and no_match_issue_code("retailer_page_editorial")
                                not in retailer_issue_codes
                                else []
                            ),
                        ]
                    }
                )
                augmented_results.append(failed_result)
                continue

            augmented_results.append(
                fetch_result.model_copy(
                    update={
                        "record": apply_retailer_editorial_record(record, retailer_record)
                    }
                )
            )

        return augmented_results


class _DefaultRetailerPageFetcher:
    def __init__(self, timeout_seconds: float, client: httpx.Client | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.client = client

    def fetch_text(self, url: str) -> str | None:
        client = self.client or httpx.Client()
        response = client.get(
            url,
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text
