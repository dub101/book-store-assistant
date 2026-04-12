from book_store_assistant.config import AppConfig
from book_store_assistant.isbn import registration_group
from book_store_assistant.sources.bne import BneSruSource
from book_store_assistant.sources.national.base import StubNationalSource
from book_store_assistant.sources.national.colombia import ColombiaISBNSource


def get_national_source(isbn: str, config: AppConfig):
    """Return the appropriate national-agency source for *isbn*, or ``None``."""
    country = registration_group(isbn)
    if country is None:
        return None
    if country == "ES":
        return BneSruSource(config)
    if country == "CO":
        return ColombiaISBNSource(config)
    return StubNationalSource(country)
