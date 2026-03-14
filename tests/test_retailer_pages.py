from book_store_assistant.sources.cache import FetchResultCache
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.retailer_pages import (
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


def test_build_retailer_search_query_uses_isbn_title_and_author() -> None:
    query = build_retailer_search_query(
        SourceBookRecord(
            source_name="google_books",
            isbn="9780306406157",
            title="Libro de prueba",
            author="Autora Ejemplo, Otra",
        )
    )

    assert query == '"9780306406157" "Libro de prueba" "Autora Ejemplo"'


def test_build_retailer_search_queries_includes_fallback_variants() -> None:
    queries = build_retailer_search_queries(
        SourceBookRecord(
            source_name="google_books",
            isbn="9780306406157",
            title="Libro de prueba",
            author="Autora Ejemplo, Otra",
        )
    )

    assert queries == [
        '"9780306406157" "Libro de prueba" "Autora Ejemplo"',
        '"9780306406157"',
        '"9780306406157" "Libro de prueba"',
        '"9780306406157" "Autora Ejemplo"',
    ]


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
    assert searcher.queries[-2:] == [
        (
            '"9780306406157" "Libro de prueba" "Autora Ejemplo"',
            ("agapea.com",),
        ),
        (
            '"9780306406157" "Libro de prueba" "Autora Ejemplo"',
            ("todostuslibros.com",),
        ),
    ]


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
    cache = FetchResultCache(tmp_path / "retailer-cache", "retailer_editorial_lookup_v1")
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
