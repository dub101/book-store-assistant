from urllib.parse import urlparse

from book_store_assistant.publisher_identity.models import PublisherIdentityResult
from book_store_assistant.sources.publisher_pages import (
    SUPPORTED_PUBLISHERS,
    match_publisher_profile,
)
from book_store_assistant.sources.results import FetchResult

PUBLISHER_DISPLAY_NAMES = {
    "penguin_random_house": "Penguin Random House Grupo Editorial",
    "planeta": "Planeta",
    "anagrama": "Anagrama",
    "galaxia_gutenberg": "Galaxia Gutenberg",
    "lectorum": "Lectorum",
    "norma_editorial": "Norma Editorial",
    "urano": "Urano",
    "harpercollins_iberica": "HarperCollins Ibérica",
    "grupo_anaya": "Grupo Anaya",
    "rba": "RBA",
    "oceano": "Océano",
    "sm": "SM",
    "kalandraka": "Kalandraka",
    "combel": "Combel",
    "nordica": "Nórdica Libros",
    "libros_del_asteroide": "Libros del Asteroide",
    "flamboyant": "Editorial Flamboyant",
    "zorro_rojo": "Libros del Zorro Rojo",
    "siruela": "Siruela",
    "acantilado_quaderns_crema": "Acantilado / Quaderns Crema",
    "alba": "Alba",
    "blackie_books": "Blackie Books",
    "capitan_swing": "Capitán Swing",
    "edelvives": "Edelvives",
    "errata_naturae": "Errata Naturae",
    "impedimenta": "Impedimenta",
    "maeva": "Maeva",
    "paginas_de_espuma": "Páginas de Espuma",
    "sexto_piso": "Sexto Piso",
}


def _clean_publisher_name(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = " ".join(value.split()).strip()
    return cleaned or None


def _split_editorial_segments(value: str) -> list[str]:
    segments = [
        _clean_publisher_name(segment.strip(" []()"))
        for segment in value.split(",")
    ]
    return [segment for segment in segments if segment]


def _resolve_imprint_name(
    editorial: str,
    publisher_display_name: str | None,
) -> str:
    segments = _split_editorial_segments(editorial)
    if len(segments) >= 2:
        return segments[-1]

    return editorial


def _publisher_from_domain(url: str | None) -> tuple[str | None, str | None]:
    if url is None:
        return None, None

    hostname = urlparse(url).hostname
    if hostname is None:
        return None, None

    normalized_hostname = hostname.casefold()
    for profile in SUPPORTED_PUBLISHERS:
        if any(
            normalized_hostname == domain.casefold()
            or normalized_hostname.endswith(f".{domain.casefold()}")
            for domain in profile.domains
        ):
            return profile.key, PUBLISHER_DISPLAY_NAMES.get(profile.key)

    return None, None


def resolve_publisher_identity(fetch_result: FetchResult) -> PublisherIdentityResult:
    if fetch_result.record is None:
        return PublisherIdentityResult(isbn=fetch_result.isbn)

    record = fetch_result.record
    editorial = _clean_publisher_name(record.editorial)
    editorial_source = record.field_sources.get("editorial", record.source_name)
    source_url = str(record.source_url) if record.source_url is not None else None
    source_url_source = record.field_sources.get("source_url", record.source_name)

    if editorial is not None:
        matched_profile = match_publisher_profile(editorial)
        normalized_editorial = editorial
        editorial_segments = _split_editorial_segments(editorial)
        if matched_profile is None and editorial_segments:
            trailing_segment = editorial_segments[-1]
            trailing_match = match_publisher_profile(trailing_segment)
            if trailing_match is not None:
                matched_profile = trailing_match
                normalized_editorial = trailing_segment

        publisher_display_name = (
            PUBLISHER_DISPLAY_NAMES.get(matched_profile.key)
            if matched_profile is not None
            else None
        )
        imprint_name = _resolve_imprint_name(normalized_editorial, publisher_display_name)
        return PublisherIdentityResult(
            isbn=fetch_result.isbn,
            publisher_name=publisher_display_name or normalized_editorial,
            imprint_name=imprint_name,
            publisher_group_key=matched_profile.key if matched_profile is not None else None,
            source_name=editorial_source,
            source_field="editorial",
            confidence=0.95 if matched_profile is not None else 0.8,
            resolution_method="editorial_field",
            evidence=[f"editorial:{editorial}"],
        )

    publisher_group_key, publisher_name = _publisher_from_domain(source_url)
    if publisher_group_key is not None:
        return PublisherIdentityResult(
            isbn=fetch_result.isbn,
            publisher_name=publisher_name,
            publisher_group_key=publisher_group_key,
            source_name=source_url_source,
            source_field="source_url",
            confidence=0.7,
            resolution_method="source_url_domain",
            evidence=[f"source_url:{source_url}"],
        )

    return PublisherIdentityResult(isbn=fetch_result.isbn)


def resolve_publisher_identities(
    fetch_results: list[FetchResult],
) -> list[PublisherIdentityResult]:
    return [resolve_publisher_identity(fetch_result) for fetch_result in fetch_results]


def attach_publisher_identities(
    fetch_results: list[FetchResult],
    publisher_identity_results: list[PublisherIdentityResult],
) -> list[FetchResult]:
    attached_results: list[FetchResult] = []

    for fetch_result, publisher_identity_result in zip(
        fetch_results,
        publisher_identity_results,
        strict=True,
    ):
        attached_results.append(
            fetch_result.model_copy(update={"publisher_identity": publisher_identity_result})
        )

    return attached_results
