import httpx

from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.retailer_pages import (
    RetailerProfile,
    apply_retailer_editorial_record,
    augment_fetch_results_with_retailer_editorials,
    build_retailer_search_queries,
    extract_retailer_page_record,
)

CASA_HTML = """
<html>
  <head>
    <title>Libro de prueba</title>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": "Libro de prueba",
        "isbn": "9780306406157",
        "author": [{"@type": "Person", "name": "Autora Ejemplo"}],
        "publisher": {"@type": "Organization", "name": "Planeta"}
      }
    </script>
  </head>
  <body>
    <p>ISBN | 9780306406157</p>
    <p>Editorial | Planeta</p>
  </body>
</html>
"""


class StubSearcher:
    def __init__(self, links: list[str]) -> None:
        self.links = links
        self.queries: list[tuple[str, tuple[str, ...]]] = []

    def search(self, query: str, allowed_domains: tuple[str, ...], limit: int = 3) -> list[str]:
        self.queries.append((query, allowed_domains))
        return self.links[:limit]


class StubPageFetcher:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.calls: list[str] = []

    def fetch_text(self, url: str) -> str | None:
        self.calls.append(url)
        return self.pages.get(url)


class RaisingSearcher:
    def search(self, query: str, allowed_domains: tuple[str, ...], limit: int = 3) -> list[str]:
        raise httpx.TimeoutException("search timed out")


class UnexpectedSearcher:
    def search(self, query: str, allowed_domains: tuple[str, ...], limit: int = 3) -> list[str]:
        raise AssertionError("retailer search should not run")


def test_build_retailer_search_queries_use_collected_record_context() -> None:
    assert build_retailer_search_queries(
        SourceBookRecord(
            source_name="google_books",
            isbn="9780306406157",
            title="Libro de prueba [Texto impreso]",
            author="Autora Ejemplo",
            editorial="Barcelona, Editorial Ariel",
        )
    ) == [
        '"9780306406157" "Libro de prueba" "Autora Ejemplo"',
        '"9780306406157"',
    ]


def test_extract_retailer_page_record_parses_bibliographic_fields() -> None:
    record = extract_retailer_page_record(
        CASA_HTML,
        "https://www.casadellibro.com/libro/123",
        "9780306406157",
        RetailerProfile("casa_del_libro", ("casadellibro.com",)),
    )

    assert record is not None
    assert record.title == "Libro de prueba"
    assert record.author == "Autora Ejemplo"
    assert record.editorial == "Planeta"


def test_apply_retailer_editorial_record_fills_missing_bibliographic_fields() -> None:
    existing = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        title="Libro de prueba",
    )
    retailer = SourceBookRecord(
        source_name="retailer_page:casa_del_libro",
        isbn="9780306406157",
        author="Autora Ejemplo",
        editorial="Planeta",
    )

    merged = apply_retailer_editorial_record(existing, retailer)

    assert merged.author == "Autora Ejemplo"
    assert merged.editorial == "Planeta"
    assert merged.field_sources["author"] == "retailer_page:casa_del_libro"


def test_augment_fetch_results_with_retailer_editorials_fills_missing_fields() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Libro de prueba",
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    searcher = StubSearcher(["https://www.casadellibro.com/libro/123"])
    page_fetcher = StubPageFetcher({"https://www.casadellibro.com/libro/123": CASA_HTML})

    augmented = augment_fetch_results_with_retailer_editorials(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=page_fetcher,
        max_retries=0,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.author == "Autora Ejemplo"
    assert augmented[0].record.editorial == "Planeta"
    assert searcher.queries[0][0] == '"9780306406157" "Libro de prueba"'


def test_augment_fetch_results_with_retailer_editorials_uses_seeded_retailer_url() -> None:
    source_url = "https://www.casadellibro.com/libro/123"
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="web_search",
                isbn="9780306406157",
                source_url=source_url,
                title="Libro de prueba",
            ),
            errors=[],
            issue_codes=[],
        )
    ]

    page_fetcher = StubPageFetcher({source_url: CASA_HTML})
    augmented = augment_fetch_results_with_retailer_editorials(
        fetch_results,
        timeout_seconds=1.0,
        searcher=UnexpectedSearcher(),
        page_fetcher=page_fetcher,
        max_retries=0,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.author == "Autora Ejemplo"
    assert augmented[0].record.editorial == "Planeta"
    assert page_fetcher.calls[0] == source_url


def test_augment_fetch_results_with_retailer_editorials_records_issue_codes_on_failure() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(source_name="google_books", isbn="9780306406157"),
            errors=[],
            issue_codes=[],
        )
    ]

    augmented = augment_fetch_results_with_retailer_editorials(
        fetch_results,
        timeout_seconds=1.0,
        searcher=RaisingSearcher(),
        page_fetcher=StubPageFetcher({}),
        max_retries=0,
    )

    assert augmented[0].record is not None
    assert "RETAILER_PAGE_SEARCH_TIMEOUT" in augmented[0].issue_codes


def test_augment_fetch_results_with_retailer_editorials_recovers_from_fetch_error() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=None,
            errors=["google_books: No Google Books match found."],
            issue_codes=["GOOGLE_BOOKS:GOOGLE_BOOKS_NO_MATCH"],
        )
    ]
    page_url = "https://www.casadellibro.com/libro/123"
    searcher = StubSearcher([page_url])
    page_fetcher = StubPageFetcher({page_url: CASA_HTML})

    augmented = augment_fetch_results_with_retailer_editorials(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=page_fetcher,
        max_retries=0,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.title == "Libro de prueba"
    assert augmented[0].record.author == "Autora Ejemplo"
    assert augmented[0].record.editorial == "Planeta"
    assert augmented[0].record.field_sources["editorial"] == "retailer_page:casa_del_libro"
