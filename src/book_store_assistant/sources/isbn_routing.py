from book_store_assistant.config import AppConfig
from book_store_assistant.isbn import registration_group
from book_store_assistant.sources.bne import BneSruSource
from book_store_assistant.sources.national.argentina import ArgentinaISBNSource
from book_store_assistant.sources.national.base import StubNationalSource
from book_store_assistant.sources.national.brazil import BrazilISBNSource
from book_store_assistant.sources.national.chile import ChileISBNSource
from book_store_assistant.sources.national.colombia import ColombiaISBNSource
from book_store_assistant.sources.national.ecuador import EcuadorISBNSource
from book_store_assistant.sources.national.mexico import MexicoISBNSource
from book_store_assistant.sources.national.peru import PeruISBNSource
from book_store_assistant.sources.national.uruguay import UruguayISBNSource
from book_store_assistant.sources.national.venezuela import VenezuelaISBNSource

_NATIONAL_SOURCES: dict[str, type] = {
    "CO": ColombiaISBNSource,
    "MX": MexicoISBNSource,
    "AR": ArgentinaISBNSource,
    "CL": ChileISBNSource,
    "PE": PeruISBNSource,
    "VE": VenezuelaISBNSource,
    "EC": EcuadorISBNSource,
    "UY": UruguayISBNSource,
    "BR": BrazilISBNSource,
}

# Countries with known ISBN agencies but no accessible public endpoint yet.
_STUB_COUNTRIES = {"BO", "GT", "CR", "PA"}


def get_national_source(isbn: str, config: AppConfig):
    """Return the appropriate national-agency source for *isbn*, or ``None``."""
    country = registration_group(isbn)
    if country is None:
        return None
    if country == "ES":
        return BneSruSource(config)
    source_cls = _NATIONAL_SOURCES.get(country)
    if source_cls is not None:
        return source_cls(config)
    if country in _STUB_COUNTRIES:
        return StubNationalSource(country)
    return StubNationalSource(country)
