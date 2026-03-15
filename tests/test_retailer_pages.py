import httpx

from book_store_assistant.sources.cache import FetchResultCache
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.retailer_pages import (
    RETAILER_EDITORIAL_CACHE_KEY,
    RetailerProfile,
    apply_retailer_editorial_record,
    augment_fetch_results_with_retailer_editorials,
    build_retailer_search_queries,
    build_retailer_search_query,
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

AGAPEA_HTML = """
<html>
  <head>
    <title>VICTORIA - 9788408295853</title>
    <meta
      name="description"
      content="Comprar el libro Victoria. Premio Planeta 2024 de Paloma
      Sanchez-Garnica, Editorial Planeta (9788408295853) con ENVIO GRATIS."
    />
  </head>
  <body>
    <p>ISBN 9788408295853</p>
  </body>
</html>
"""


class StubSearcher:
    def __init__(self, links: list[str]) -> None:
        self.links = links
        self.queries: list[tuple[str, tuple[str, ...]]] = []

    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = 3,
    ) -> list[str]:
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
    def __init__(self) -> None:
        self.queries: list[tuple[str, tuple[str, ...]]] = []

    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = 3,
    ) -> list[str]:
        self.queries.append((query, allowed_domains))
        raise httpx.TimeoutException("search timed out")


def test_build_retailer_search_query_uses_exact_isbn_only() -> None:
    query = build_retailer_search_query(
        SourceBookRecord(
            source_name="google_books",
            isbn="9780306406157",
            title="Libro de prueba",
            author="Autora Ejemplo, Otra",
        )
    )

    assert query == '"9780306406157"'


def test_build_retailer_search_queries_use_exact_isbn_only() -> None:
    queries = build_retailer_search_queries(
        SourceBookRecord(
            source_name="google_books",
            isbn="9780306406157",
            title="Libro de prueba",
            author="Autora Ejemplo, Otra",
        )
    )

    assert queries == ['"9780306406157"']


def test_extract_retailer_page_record_parses_editorial() -> None:
    record = extract_retailer_page_record(
        CASA_HTML,
        "https://www.casadellibro.com/libro/123",
        "9780306406157",
        profile=RetailerProfile("casa_del_libro", ("casadellibro.com",)),
    )

    assert record is not None
    assert record.editorial == "Planeta"
    assert record.author == "Autora Ejemplo"


def test_extract_retailer_page_record_parses_agapea_editorial_from_meta_description() -> None:
    record = extract_retailer_page_record(
        AGAPEA_HTML,
        "https://www.agapea.com/buscador/buscador.php?texto=9788408295853",
        "9788408295853",
        profile=RetailerProfile("agapea", ("agapea.com",)),
    )

    assert record is not None
    assert record.author == "Paloma Sanchez-Garnica"
    assert record.editorial == "Editorial Planeta"


def test_apply_retailer_editorial_record_fills_missing_editorial() -> None:
    existing = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        title="Libro de prueba",
        author="Autora Ejemplo",
    )
    retailer = SourceBookRecord(
        source_name="retailer_page:casa_del_libro",
        isbn="9780306406157",
        editorial="Planeta",
    )

    merged = apply_retailer_editorial_record(existing, retailer)

    assert merged.editorial == "Planeta"
    assert merged.field_sources["editorial"] == "retailer_page:casa_del_libro"


def test_augment_fetch_results_with_retailer_editorials_fills_missing_author_when_editorial_exists(
) -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Libro de prueba",
                editorial="Planeta",
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
    assert augmented[0].record.field_sources["author"] == "retailer_page:casa_del_libro"


def test_augment_fetch_results_with_retailer_editorials_fills_missing_editorial() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Libro de prueba",
                author="Autora Ejemplo",
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
    assert augmented[0].record.editorial == "Planeta"
    assert augmented[0].record.field_sources["editorial"] == "retailer_page:casa_del_libro"


def test_augment_fetch_results_with_retailer_editorials_uses_direct_agapea_lookup_before_search(
) -> None:
    fetch_results = [
        FetchResult(
            isbn="9788408295853",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9788408295853",
                title="Victoria. Premio Planeta 2024",
                author="Paloma Sanchez-Garnica",
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    searcher = StubSearcher([])
    page_fetcher = StubPageFetcher(
        {"https://www.agapea.com/buscador/buscador.php?texto=9788408295853": AGAPEA_HTML}
    )

    augmented = augment_fetch_results_with_retailer_editorials(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=page_fetcher,
        max_retries=0,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.editorial == "Editorial Planeta"
    assert searcher.queries == []


def test_augment_fetch_results_with_retailer_editorials_searches_new_retailer_domains() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Libro de prueba",
                author="Autora Ejemplo",
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    searcher = StubSearcher(
        [
            "https://www.agapea.com/libros/libro-de-prueba-9780306406157-i.htm",
            "https://www.todostuslibros.com/libros/libro-de-prueba_9780306406157",
        ]
    )
    page_fetcher = StubPageFetcher({})

    augmented = augment_fetch_results_with_retailer_editorials(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=page_fetcher,
        max_retries=0,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.editorial is None
    assert searcher.queries[0] == (
        '"9780306406157"',
        ("agapea.com",),
    )
    assert searcher.queries[1] == (
        '"9780306406157"',
        (
            "buscalibre.com",
            "buscalibre.cl",
            "buscalibre.com.co",
            "buscalibre.com.mx",
            "buscalibre.pe",
            "buscalibre.us",
        ),
    )
    assert searcher.queries[-1] == (
        '"9780306406157"',
        ("todostuslibros.com",),
    )


def test_augment_fetch_results_with_retailer_editorials_reuses_cached_negative_result(
    tmp_path,
) -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Libro de prueba",
                author="Autora Ejemplo",
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    cache = FetchResultCache(tmp_path / "retailer-cache", RETAILER_EDITORIAL_CACHE_KEY)
    cache.set(
        FetchResult(
            isbn="9780306406157",
            record=None,
            errors=[],
            issue_codes=["RETAILER_PAGE_SEARCH_TIMEOUT", "RETAILER_PAGE_EDITORIAL_NO_MATCH"],
        ),
        allow_empty=True,
    )
    searcher = StubSearcher(["https://www.casadellibro.com/libro/123"])

    augmented = augment_fetch_results_with_retailer_editorials(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=StubPageFetcher({}),
        cache=cache,
        cache_ttl_seconds=3600,
        max_retries=0,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.editorial is None
    assert augmented[0].issue_codes == [
        "RETAILER_PAGE_SEARCH_TIMEOUT",
        "RETAILER_PAGE_EDITORIAL_NO_MATCH",
    ]
    assert searcher.queries == []


def test_augment_fetch_results_with_retailer_editorials_honors_search_budget() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Libro de prueba",
                author="Autora Ejemplo",
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    searcher = StubSearcher([])

    augmented = augment_fetch_results_with_retailer_editorials(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=StubPageFetcher({}),
        max_retries=0,
        max_search_attempts_per_record=1,
    )

    assert augmented[0].issue_codes == [
        "RETAILER_PAGE_SEARCH_BUDGET_EXHAUSTED",
        "RETAILER_PAGE_EDITORIAL_NO_MATCH",
    ]
    assert len(searcher.queries) == 1


def test_augment_fetch_results_with_retailer_editorials_does_not_spend_budget_on_search_timeouts(
) -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Libro de prueba",
                author="Autora Ejemplo",
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    searcher = RaisingSearcher()

    augmented = augment_fetch_results_with_retailer_editorials(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=StubPageFetcher({}),
        max_retries=0,
        max_search_attempts_per_record=1,
    )

    assert "RETAILER_PAGE_SEARCH_BUDGET_EXHAUSTED" not in augmented[0].issue_codes
    assert "RETAILER_PAGE_SEARCH_TIMEOUT" in augmented[0].issue_codes
    assert "RETAILER_PAGE_EDITORIAL_NO_MATCH" in augmented[0].issue_codes
    assert len(searcher.queries) > 1


def test_augment_fetch_results_with_retailer_editorials_honors_fetch_budget() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="Libro de prueba",
                author="Autora Ejemplo",
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    searcher = StubSearcher(["https://www.casadellibro.com/libro/123"])
    page_fetcher = StubPageFetcher({"https://www.casadellibro.com/libro/123": "<html></html>"})

    augmented = augment_fetch_results_with_retailer_editorials(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=page_fetcher,
        max_retries=0,
        max_fetch_attempts_per_record=0,
    )

    assert augmented[0].issue_codes == [
        "RETAILER_PAGE_FETCH_BUDGET_EXHAUSTED",
        "RETAILER_PAGE_EDITORIAL_NO_MATCH",
    ]
    assert page_fetcher.calls == []
