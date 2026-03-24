import json
import re
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from html import unescape
from typing import TypedDict, TypeVar
from urllib.parse import urlparse

import httpx
from pydantic import HttpUrl, TypeAdapter

from book_store_assistant.isbn import normalize_isbn
from book_store_assistant.sources.diagnostics import changed_record_fields, with_diagnostic
from book_store_assistant.sources.exact_page_lookup import lookup_exact_page_record
from book_store_assistant.sources.issues import classify_http_issue, no_match_issue_code
from book_store_assistant.sources.language_codes import normalize_language_code
from book_store_assistant.sources.merge import merge_source_records
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.page_descriptions import (
    extract_description_candidates_from_html,
)
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.search_backend import (
    DEFAULT_BROWSER_HEADERS,
    SEARCH_RESULT_LIMIT,
    PageContentFetcher,
    SearchBackend,
    _is_allowed_domain,
    build_default_search_backend,
)

BOOKISH_TYPES = {"book", "product", "creativework"}
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
AUTHOR_LABEL_PATTERN = re.compile(
    r"(?:autor(?:es)?|author)\s*[:|]\s*([^\n|]+)",
    re.IGNORECASE,
)
SUBJECT_LABEL_PATTERN = re.compile(
    r"(?:tem[aá]ticas?|tem[aá]tica|materia(?:s)?|categor[ií]as?|g[eé]nero)\s*[:|]\s*([^\n|]+)",
    re.IGNORECASE,
)
HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)
PublisherPageStatusCallback = Callable[[str], None]
PUBLISHER_PAGE_ISBN_MISMATCH = "PUBLISHER_PAGE_ISBN_MISMATCH"
RETRYABLE_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
T = TypeVar("T")


@dataclass(frozen=True)
class PublisherProfile:
    key: str
    domains: tuple[str, ...]
    editorial_aliases: tuple[str, ...]


SUPPORTED_PUBLISHERS_BASE: tuple[PublisherProfile, ...] = (
    PublisherProfile(
        key="penguin_random_house",
        domains=("penguinlibros.com", "megustaleer.com"),
        editorial_aliases=(
            "penguin random house",
            "penguin random house grupo editorial",
            "random house",
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
            "planeta comic",
            "planeta cómic",
            "planeta audio",
            "booket",
            "destino",
            "ediciones destino",
            "ediciones b",
            "espasa",
            "espasa libros",
            "seix barral",
            "ariel",
            "editorial ariel",
            "paidos",
            "paidós",
            "ediciones paidos",
            "ediciones paidós",
            "editorial paidos",
            "editorial paidós",
            "tusquets",
            "tusquets editores",
            "austral",
            "alienta",
            "alienta editorial",
            "gestion 2000",
            "gestión 2000",
            "lunwerg",
            "lunwerg editores",
            "booket",
            "critica",
            "crítica",
            "editorial critica",
            "editorial crítica",
            "cupula",
            "cúpula",
            "deusto",
            "destino infantil juvenil",
            "ediciones peninsula",
            "galera",
            "geo planeta",
            "geoplaneta",
            "grupo planeta",
            "grupo planeta gbs",
            "grupo planeta spain",
            "libros cupula",
            "libros cúpula",
            "peninsula",
            "península",
            "temas de hoy",
            "ediciones temas de hoy",
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
    PublisherProfile(
        key="harpercollins_iberica",
        domains=("harpercollinsiberica.com",),
        editorial_aliases=(
            "harpercollins",
            "harper collins",
            "harpercollins iberica",
            "harper collins iberica",
            "harpercollins ibérica",
            "harper collins ibérica",
        ),
    ),
    PublisherProfile(
        key="grupo_anaya",
        domains=("anaya.es", "anayainfantilyjuvenil.com"),
        editorial_aliases=(
            "anaya",
            "grupo anaya",
            "alianza editorial",
            "alianza",
            "catedra",
            "cátedra",
            "piramide",
            "pirámide",
            "tecnos",
            "oberon",
            "xerais",
        ),
    ),
    PublisherProfile(
        key="rba",
        domains=("rbalibros.com",),
        editorial_aliases=(
            "rba",
            "rba libros",
            "rba coleccionables",
            "rba integral",
            "rba bolsillo",
            "gredos",
        ),
    ),
    PublisherProfile(
        key="oceano",
        domains=("oceano.com",),
        editorial_aliases=(
            "oceano",
            "océano",
            "oceano gran travesia",
            "océano gran travesía",
            "gran travesia",
            "gran travesía",
        ),
    ),
    PublisherProfile(
        key="sm",
        domains=("grupo-sm.com", "literaturasm.com"),
        editorial_aliases=(
            "sm",
            "ediciones sm",
            "fundacion sm",
            "fundación sm",
            "el barco de vapor",
            "gran angular",
        ),
    ),
    PublisherProfile(
        key="kalandraka",
        domains=("kalandraka.com",),
        editorial_aliases=(
            "kalandraka",
            "editorial kalandraka",
        ),
    ),
    PublisherProfile(
        key="combel",
        domains=("combeleditorial.com",),
        editorial_aliases=(
            "combel",
            "combel editorial",
        ),
    ),
    PublisherProfile(
        key="nordica",
        domains=("nordicalibros.com",),
        editorial_aliases=(
            "nordica",
            "nórdica",
            "nordica libros",
            "nórdica libros",
        ),
    ),
    PublisherProfile(
        key="libros_del_asteroide",
        domains=("librosdelasteroide.com",),
        editorial_aliases=(
            "asteroide",
            "libros del asteroide",
        ),
    ),
    PublisherProfile(
        key="flamboyant",
        domains=("editorialflamboyant.com",),
        editorial_aliases=(
            "flamboyant",
            "editorial flamboyant",
        ),
    ),
    PublisherProfile(
        key="zorro_rojo",
        domains=("librosdelzorrorojo.com",),
        editorial_aliases=(
            "zorro rojo",
            "libros del zorro rojo",
        ),
    ),
    PublisherProfile(
        key="siruela",
        domains=("siruela.com",),
        editorial_aliases=(
            "siruela",
            "editorial siruela",
        ),
    ),
)

IMPRINT_TO_LOOKUP = {
    "acantilado": "acantilado_quaderns_crema",
    "alba editorial": "alba",
    "anagrama": "anagrama",
    "blackie books": "blackie_books",
    "capitan swing": "capitan_swing",
    "combel editorial": "combel",
    "edelvives": "edelvives",
    "errata naturae": "errata_naturae",
    "editorial flamboyant": "flamboyant",
    "galaxia gutenberg": "galaxia_gutenberg",
    "adn": "grupo_anaya",
    "algaida": "grupo_anaya",
    "alianza editorial": "grupo_anaya",
    "anaya": "grupo_anaya",
    "anaya ele": "grupo_anaya",
    "anaya infantil y juvenil": "grupo_anaya",
    "bruno": "grupo_anaya",
    "harlequin": "harpercollins_iberica",
    "harpercollins iberica": "harpercollins_iberica",
    "impedimenta": "impedimenta",
    "kalandraka": "kalandraka",
    "lectorum": "lectorum",
    "libros del asteroide": "libros_del_asteroide",
    "maeva": "maeva",
    "maeva young": "maeva",
    "nordica libros": "nordica",
    "norma editorial": "norma_editorial",
    "oceano": "oceano",
    "oceano gran travesia": "oceano",
    "oceano travesia": "oceano",
    "paginas de espuma": "paginas_de_espuma",
    "alfaguara": "penguin_random_house",
    "debolsillo": "penguin_random_house",
    "lumen": "penguin_random_house",
    "plaza y janes": "penguin_random_house",
    "reservoir books": "penguin_random_house",
    "salamandra": "penguin_random_house",
    "suma": "penguin_random_house",
    "booket": "planeta",
    "destino": "planeta",
    "ediciones destino": "planeta",
    "editorial planeta": "planeta",
    "espasa": "planeta",
    "espasa libros": "planeta",
    "seix barral": "planeta",
    "editorial ariel": "planeta",
    "editorial crítica": "planeta",
    "editorial critica": "planeta",
    "editorial paidós": "planeta",
    "editorial paidos": "planeta",
    "ediciones paidós": "planeta",
    "ediciones paidos": "planeta",
    "ediciones temas de hoy": "planeta",
    "gestión 2000": "planeta",
    "gestion 2000": "planeta",
    "geoplaneta": "planeta",
    "lunwerg": "planeta",
    "lunwerg editores": "planeta",
    "paidós": "planeta",
    "planeta audio": "planeta",
    "planeta cómic": "planeta",
    "planeta comic": "planeta",
    "tusquets editores": "planeta",
    "gredos": "rba",
    "integral": "rba",
    "rba infantil": "rba",
    "rba libros": "rba",
    "serie negra": "rba",
    "sexto piso": "sexto_piso",
    "ediciones siruela": "siruela",
    "literatura sm": "sm",
    "sm": "sm",
    "books4pocket": "urano",
    "ediciones urano": "urano",
    "empresa activa": "urano",
    "puck": "urano",
    "tendencias": "urano",
    "titania": "urano",
    "umbriel": "urano",
    "libros del zorro rojo": "zorro_rojo",
}

class LookupDomainConfig(TypedDict):
    canonical_domain: str
    alternative_domains: tuple[str, ...]


LOOKUP_TO_DOMAINS: dict[str, LookupDomainConfig] = {
    "acantilado_quaderns_crema": {
        "canonical_domain": "acantilado.es",
        "alternative_domains": (),
    },
    "alba": {
        "canonical_domain": "albaeditorial.es",
        "alternative_domains": (),
    },
    "anagrama": {
        "canonical_domain": "anagrama-ed.es",
        "alternative_domains": (),
    },
    "blackie_books": {
        "canonical_domain": "blackiebooks.org",
        "alternative_domains": (),
    },
    "capitan_swing": {
        "canonical_domain": "capitanswing.com",
        "alternative_domains": (),
    },
    "combel": {
        "canonical_domain": "combeleditorial.com",
        "alternative_domains": (),
    },
    "edelvives": {
        "canonical_domain": "edelvives.com",
        "alternative_domains": (),
    },
    "errata_naturae": {
        "canonical_domain": "erratanaturae.com",
        "alternative_domains": (),
    },
    "flamboyant": {
        "canonical_domain": "editorialflamboyant.com",
        "alternative_domains": (),
    },
    "galaxia_gutenberg": {
        "canonical_domain": "galaxiagutenberg.com",
        "alternative_domains": (),
    },
    "grupo_anaya": {
        "canonical_domain": "anaya.es",
        "alternative_domains": ("anayainfantilyjuvenil.com",),
    },
    "harpercollins_iberica": {
        "canonical_domain": "harpercollinsiberica.com",
        "alternative_domains": (),
    },
    "impedimenta": {
        "canonical_domain": "impedimenta.es",
        "alternative_domains": (),
    },
    "kalandraka": {
        "canonical_domain": "kalandraka.com",
        "alternative_domains": (),
    },
    "lectorum": {
        "canonical_domain": "lectorum.com",
        "alternative_domains": (),
    },
    "libros_del_asteroide": {
        "canonical_domain": "librosdelasteroide.com",
        "alternative_domains": (),
    },
    "maeva": {
        "canonical_domain": "maeva.es",
        "alternative_domains": (),
    },
    "nordica": {
        "canonical_domain": "nordicalibros.com",
        "alternative_domains": (),
    },
    "norma_editorial": {
        "canonical_domain": "normaeditorial.com",
        "alternative_domains": (),
    },
    "oceano": {
        "canonical_domain": "oceano.com",
        "alternative_domains": (),
    },
    "paginas_de_espuma": {
        "canonical_domain": "paginasdeespuma.com",
        "alternative_domains": (),
    },
    "penguin_random_house": {
        "canonical_domain": "penguinlibros.com",
        "alternative_domains": ("megustaleer.com",),
    },
    "planeta": {
        "canonical_domain": "planetadelibros.com",
        "alternative_domains": (),
    },
    "rba": {
        "canonical_domain": "rbalibros.com",
        "alternative_domains": (),
    },
    "sexto_piso": {
        "canonical_domain": "sextopiso.es",
        "alternative_domains": (),
    },
    "siruela": {
        "canonical_domain": "siruela.com",
        "alternative_domains": (),
    },
    "sm": {
        "canonical_domain": "literaturasm.com",
        "alternative_domains": ("grupo-sm.com",),
    },
    "urano": {
        "canonical_domain": "edicionesurano.com",
        "alternative_domains": (),
    },
    "zorro_rojo": {
        "canonical_domain": "librosdelzorrorojo.com",
        "alternative_domains": (),
    },
}


def _merge_distinct(values: tuple[str, ...], extra_values: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = list(values)
    seen = {item.casefold() for item in values}

    for value in extra_values:
        if value.casefold() in seen:
            continue
        seen.add(value.casefold())
        merged.append(value)

    return tuple(merged)


def _build_lookup_profiles() -> tuple[PublisherProfile, ...]:
    aliases_by_lookup: dict[str, list[str]] = {}

    for imprint, lookup_key in IMPRINT_TO_LOOKUP.items():
        aliases_by_lookup.setdefault(lookup_key, []).append(imprint)

    profiles: list[PublisherProfile] = []
    for lookup_key, domain_config in LOOKUP_TO_DOMAINS.items():
        profiles.append(
            PublisherProfile(
                key=lookup_key,
                domains=(
                    domain_config["canonical_domain"],
                    *domain_config["alternative_domains"],
                ),
                editorial_aliases=tuple(aliases_by_lookup.get(lookup_key, ())),
            )
        )

    return tuple(profiles)


def _merge_publisher_profiles(
    base_profiles: tuple[PublisherProfile, ...],
    extra_profiles: tuple[PublisherProfile, ...],
) -> tuple[PublisherProfile, ...]:
    merged_profiles: list[PublisherProfile] = list(base_profiles)
    index_by_key = {profile.key: index for index, profile in enumerate(merged_profiles)}

    for profile in extra_profiles:
        existing_index = index_by_key.get(profile.key)
        if existing_index is None:
            index_by_key[profile.key] = len(merged_profiles)
            merged_profiles.append(profile)
            continue

        existing_profile = merged_profiles[existing_index]
        merged_profiles[existing_index] = PublisherProfile(
            key=existing_profile.key,
            domains=_merge_distinct(existing_profile.domains, profile.domains),
            editorial_aliases=_merge_distinct(
                existing_profile.editorial_aliases,
                profile.editorial_aliases,
            ),
        )

    return tuple(merged_profiles)


ACTIVE_LOOKUP_KEYS = frozenset(profile.key for profile in SUPPORTED_PUBLISHERS_BASE)

SUPPORTED_PUBLISHERS: tuple[PublisherProfile, ...] = _merge_publisher_profiles(
    SUPPORTED_PUBLISHERS_BASE,
    tuple(
        profile for profile in _build_lookup_profiles()
        if profile.key in ACTIVE_LOOKUP_KEYS
    ),
)


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


def _split_category_text(value: str) -> list[str]:
    parts = re.split(r"[|;,>/]+", value)
    return [part.strip() for part in parts if part.strip()]


def _clean_category_values(values: list[str]) -> list[str]:
    cleaned_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue

        key = cleaned.casefold()
        if key in seen:
            continue

        seen.add(key)
        cleaned_values.append(cleaned)

    return cleaned_values


def _extract_category_values(value: object) -> list[str]:
    if isinstance(value, str):
        return _clean_category_values(_split_category_text(value))

    if isinstance(value, dict):
        extracted = _extract_string(value)
        if extracted is None:
            return []
        return _clean_category_values(_split_category_text(extracted))

    if isinstance(value, list):
        collected: list[str] = []
        for item in value:
            collected.extend(_extract_category_values(item))
        return _clean_category_values(collected)

    return []


def _extract_subject_candidates_from_text(html: str) -> list[str]:
    text = _clean_text(html)
    match = SUBJECT_LABEL_PATTERN.search(text)
    if match is None:
        return []

    return _clean_category_values(_split_category_text(match.group(1)))


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
                    categories=_clean_category_values(
                        [
                            *_extract_category_values(bookish.get("genre")),
                            *_extract_category_values(bookish.get("keywords")),
                            *_extract_category_values(bookish.get("about")),
                        ]
                    ),
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
    return f'"{record.isbn}"'


def build_publisher_search_queries(
    record: SourceBookRecord,
    profile: PublisherProfile | None = None,
) -> list[str]:
    del profile
    return [build_publisher_search_query(record)]


def _score_candidate_url(url: str, record: SourceBookRecord) -> tuple[int, int, int]:
    return (1 if record.isbn in url else 0, 0, 0)


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


def _extract_author_from_text(html: str) -> str | None:
    text = _clean_text(html)
    match = AUTHOR_LABEL_PATTERN.search(text)
    if match is None:
        return None

    author = match.group(1).strip(" .|")
    return author or None


def _extract_isbn_candidates(html: str) -> set[str]:
    return {
        normalize_isbn(match.group(0))
        for match in ISBN_PATTERN.finditer(_clean_text(html))
        if normalize_isbn(match.group(0))
    }


def _publisher_page_validator(
    html: str,
    _page_url: str,
    record: SourceBookRecord,
    _profile: PublisherProfile,
) -> tuple[bool, list[str]]:
    if normalize_isbn(record.isbn) not in _extract_isbn_candidates(html):
        return False, [PUBLISHER_PAGE_ISBN_MISMATCH]

    return True, []


def _publisher_lookup_issue_code(code: str) -> str:
    if code == "PAGE_SEARCH_BUDGET_EXHAUSTED":
        return "PUBLISHER_PAGE_SEARCH_BUDGET_EXHAUSTED"
    if code == "PAGE_FETCH_BUDGET_EXHAUSTED":
        return "PUBLISHER_PAGE_FETCH_BUDGET_EXHAUSTED"
    return code


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
    text_categories = _extract_subject_candidates_from_text(html)

    if json_ld_record is not None:
        field_sources = _seed_field_sources(json_ld_record)
        return json_ld_record.model_copy(
            update={
                "source_name": f"publisher_page:{profile.key}",
                "isbn": isbn,
                "source_url": _coerce_http_url(page_url),
                "synopsis": json_ld_record.synopsis or synopsis,
                "editorial": json_ld_record.editorial or _extract_editorial_from_text(html),
                "categories": _merge_categories(json_ld_record.categories, text_categories),
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
        author=_extract_author_from_text(html),
        editorial=_extract_editorial_from_text(html),
        synopsis=synopsis,
        categories=text_categories,
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

    existing_synopsis = existing_record.synopsis.strip()
    publisher_synopsis = publisher_record.synopsis.strip()
    if not existing_synopsis:
        return True

    # Replace clipped teaser text with a materially richer official synopsis.
    if len(existing_synopsis) < 140 and len(publisher_synopsis) > len(existing_synopsis) + 40:
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


def _retry_delay_seconds(
    attempt: int,
    backoff_seconds: float,
    exc: httpx.HTTPError,
) -> float:
    if isinstance(exc, httpx.HTTPStatusError):
        retry_after = exc.response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                parsed_retry_after = float(retry_after)
            except ValueError:
                pass
            else:
                if parsed_retry_after >= 0:
                    return parsed_retry_after

    return backoff_seconds * (2**attempt)


def _should_retry_http_error(exc: httpx.HTTPError, attempt: int, max_retries: int) -> bool:
    if attempt >= max_retries:
        return False

    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_HTTP_STATUS_CODES

    return isinstance(exc, httpx.TransportError)


def _run_with_retry(
    operation: Callable[[], T],
    source_name: str,
    max_retries: int,
    backoff_seconds: float,
    sleep: Callable[[float], None],
) -> tuple[T | None, list[str]]:
    issue_codes: list[str] = []

    for attempt in range(max_retries + 1):
        try:
            return operation(), issue_codes
        except httpx.HTTPError as exc:
            issue_codes = _merge_issue_codes(issue_codes, classify_http_issue(source_name, exc))
            if not _should_retry_http_error(exc, attempt, max_retries):
                return None, issue_codes
            sleep(_retry_delay_seconds(attempt, backoff_seconds, exc))

    return None, issue_codes


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

def _needs_publisher_lookup(record: SourceBookRecord) -> bool:
    return bool(record.editorial) and (not record.title or not record.author)


def _candidate_publisher_profiles(record: SourceBookRecord) -> list[PublisherProfile]:
    matched_profile = match_publisher_profile(record.editorial)
    return [matched_profile] if matched_profile is not None else []


def _build_direct_publisher_urls(
    record: SourceBookRecord,
    profile: PublisherProfile,
) -> list[str]:
    if record.source_url is None:
        return []

    source_url = str(record.source_url)
    if not _is_allowed_domain(source_url, profile.domains):
        return []

    return [source_url]


def augment_fetch_results_with_publisher_pages(
    fetch_results: list[FetchResult],
    timeout_seconds: float,
    searcher: SearchBackend | None = None,
    page_fetcher: PageContentFetcher | None = None,
    on_status_update: PublisherPageStatusCallback | None = None,
    max_retries: int = 2,
    backoff_seconds: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
    eligible_isbns: set[str] | None = None,
    force_lookup_isbns: set[str] | None = None,
    max_profiles_per_record: int | None = None,
    max_search_attempts_per_record: int | None = None,
    max_fetch_attempts_per_record: int | None = None,
) -> list[FetchResult]:
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        active_searcher = searcher or build_default_search_backend(
            timeout_seconds,
            client=client,
        )
        active_page_fetcher = page_fetcher or _DefaultPageFetcher(timeout_seconds, client=client)
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
            if eligible_isbns is not None and record.isbn not in eligible_isbns:
                augmented_results.append(fetch_result)
                continue

            force_lookup = force_lookup_isbns is not None and record.isbn in force_lookup_isbns
            if not force_lookup and not _needs_publisher_lookup(record):
                augmented_results.append(fetch_result)
                continue

            candidate_profiles = _candidate_publisher_profiles(record)
            if max_profiles_per_record is not None and max_profiles_per_record >= 0:
                candidate_profiles = candidate_profiles[:max_profiles_per_record]
            if not candidate_profiles:
                augmented_results.append(fetch_result)
                continue

            if on_status_update is not None:
                on_status_update(
                    f"Publisher lookup {index}/{len(fetch_results)}: {record.isbn}"
                )

            attempted_search_queries: list[str] = []
            attempted_search_domains: list[list[str]] = []
            candidate_urls: list[str] = []
            attempted_fetch_urls: list[str] = []
            fetched_domains: list[str] = []

            def _search_with_trace(
                query: str,
                allowed_domains: tuple[str, ...],
                limit: int = SEARCH_RESULT_LIMIT,
            ) -> list[str]:
                attempted_search_queries.append(query)
                attempted_search_domains.append(list(allowed_domains))
                result_urls = active_searcher.search(query, allowed_domains, limit)
                for result_url in result_urls:
                    if result_url not in candidate_urls:
                        candidate_urls.append(result_url)
                return result_urls

            def _fetch_with_trace(url: str) -> str | None:
                attempted_fetch_urls.append(url)
                hostname = (urlparse(url).hostname or "").casefold()
                if hostname and hostname not in fetched_domains:
                    fetched_domains.append(hostname)
                return active_page_fetcher.fetch_text(url)

            publisher_record, raw_issue_codes = lookup_exact_page_record(
                record,
                candidate_profiles,
                search_queries=build_publisher_search_queries,
                direct_query_urls=_build_direct_publisher_urls,
                extract_record=extract_publisher_page_record,
                search=_search_with_trace,
                fetch_text=_fetch_with_trace,
                run_with_retry=_run_with_retry,
                rank_candidate_urls=_rank_candidate_urls,
                is_allowed_domain=_is_allowed_domain,
                search_issue_source="publisher_page_search",
                fetch_issue_source="publisher_page_fetch",
                page_validator=_publisher_page_validator,
                search_result_limit=SEARCH_RESULT_LIMIT,
                max_retries=max_retries,
                backoff_seconds=backoff_seconds,
                sleep=sleep,
                max_search_attempts_per_record=max_search_attempts_per_record,
                max_fetch_attempts_per_record=max_fetch_attempts_per_record,
            )
            publisher_issue_codes = [
                _publisher_lookup_issue_code(code)
                for code in raw_issue_codes
            ]

            if publisher_record is None:
                failed_result = with_diagnostic(
                    fetch_result,
                    "publisher_pages",
                    "completed",
                    forced=force_lookup,
                    search_queries=attempted_search_queries,
                    search_domains=attempted_search_domains,
                    search_attempts=len(attempted_search_queries),
                    candidate_urls=candidate_urls,
                    fetched_domains=fetched_domains,
                    fetch_attempts=len(attempted_fetch_urls),
                    publisher_match=False,
                    publisher_profiles=[profile.key for profile in candidate_profiles],
                    issue_codes=publisher_issue_codes,
                ).model_copy(
                    update={
                        "issue_codes": _merge_issue_codes(
                            fetch_result.issue_codes,
                            publisher_issue_codes,
                            [no_match_issue_code("publisher_page")],
                        )
                    }
                )
                augmented_results.append(failed_result)
                continue

            merged_record = apply_publisher_page_record(record, publisher_record)
            augmented_results.append(
                with_diagnostic(
                    fetch_result,
                    "publisher_pages",
                    "completed",
                    forced=force_lookup,
                    search_queries=attempted_search_queries,
                    search_domains=attempted_search_domains,
                    search_attempts=len(attempted_search_queries),
                    candidate_urls=candidate_urls,
                    fetched_domains=fetched_domains,
                    fetch_attempts=len(attempted_fetch_urls),
                    publisher_match=True,
                    publisher_source=publisher_record.source_name,
                    publisher_editorial=publisher_record.editorial,
                    publisher_source_url=(
                        str(publisher_record.source_url)
                        if publisher_record.source_url is not None
                        else None
                    ),
                    publisher_profiles=[profile.key for profile in candidate_profiles],
                    changed_fields=changed_record_fields(record, merged_record),
                ).model_copy(
                    update={"record": merged_record}
                )
            )

        return augmented_results


class _DefaultPageFetcher:
    def __init__(self, timeout_seconds: float, client: httpx.Client | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.client = client

    def fetch_text(self, url: str) -> str | None:
        try:
            client = self.client or httpx.Client()
            response = client.get(
                url,
                headers=DEFAULT_BROWSER_HEADERS,
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise

        return response.text
