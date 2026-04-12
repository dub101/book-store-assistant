import xml.etree.ElementTree as ET

from pydantic import HttpUrl, TypeAdapter

from book_store_assistant.sources.language_codes import normalize_language_code
from book_store_assistant.sources.models import SourceBookRecord

DC_NAMESPACE = "{http://purl.org/dc/elements/1.1/}"
HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)

_BNE_CATALOG_NOTE_PATTERNS = [
    "bibliograf",
    "narrador",
    "traducci",
    "trad. de",
    "trad.:",
    "il. de",
    "ilustraciones",
    "p.",
    "título original",
    "titulo original",
    "en portada",
    "random house",
    "penguin",
    "grupo editorial",
    "ed. lit",
    "edición de",
    "edicion de",
    "prólogo",
    "prologo",
]
_BNE_SYNOPSIS_MIN_LENGTH = 80


def _is_bne_catalog_note(text: str) -> bool:
    lower = text.strip().lower()
    if any(pat in lower for pat in _BNE_CATALOG_NOTE_PATTERNS):
        return True
    if len(text.strip()) < _BNE_SYNOPSIS_MIN_LENGTH:
        return True
    return False


def _find_first_text(element: ET.Element, field_name: str) -> str | None:
    for value in element.findall(f".//{DC_NAMESPACE}{field_name}"):
        if value.text and value.text.strip():
            return value.text.strip()

    return None


def _find_all_text(element: ET.Element, field_name: str) -> list[str]:
    values: list[str] = []

    for node in element.findall(f".//{DC_NAMESPACE}{field_name}"):
        if node.text and node.text.strip():
            values.append(node.text.strip())

    return values


def _find_source_url(identifiers: list[str]) -> HttpUrl | None:
    for identifier in identifiers:
        if not identifier.startswith(("http://", "https://")):
            continue

        try:
            return HTTP_URL_ADAPTER.validate_python(identifier)
        except ValueError:
            continue

    return None


def parse_bne_sru_payload(payload: str, isbn: str) -> SourceBookRecord | None:
    root = ET.fromstring(payload)
    records = root.findall(".//{http://www.loc.gov/zing/srw/}record")
    if not records:
        return None

    record = records[0]
    title = _find_first_text(record, "title")
    if title is None:
        return None

    creators = _find_all_text(record, "creator")
    publishers = _find_all_text(record, "publisher")
    subjects = _find_all_text(record, "subject")
    identifiers = _find_all_text(record, "identifier")
    source_url = _find_source_url(identifiers)

    raw_description = _find_first_text(record, "description")
    synopsis = None
    if raw_description and not _is_bne_catalog_note(raw_description):
        synopsis = raw_description

    return SourceBookRecord(
        source_name="bne",
        isbn=isbn,
        source_url=source_url,
        raw_source_payload=None,
        title=title,
        author=", ".join(creators) if creators else None,
        editorial=", ".join(publishers) if publishers else None,
        synopsis=synopsis,
        categories=subjects,
        language=normalize_language_code(_find_first_text(record, "language")),
    )
