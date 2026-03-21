from book_store_assistant.sources.cache import FetchResultCache
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.publisher_discovery import (
    PUBLISHER_DISCOVERY_CACHE_KEY,
    augment_fetch_results_with_publisher_discovery,
)
from book_store_assistant.sources.results import FetchResult

PENGUIN_HTML = """
<html lang="es">
  <head>
    <title>El nino que perdio la guerra | Penguin Libros</title>
    <meta property="og:title" content="El nino que perdio la guerra" />
    <meta
      property="og:description"
      content="Madrid, invierno de 1938. Clotilde intenta evitar que su hijo sea
      enviado a Moscu mientras la guerra se derrumba."
    />
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": "El nino que perdio la guerra",
        "isbn": "9788401027970",
        "author": [{"@type": "Person", "name": "Julia Navarro"}],
        "publisher": {"@type": "Organization", "name": "Plaza & Janes"},
        "description": "Madrid, invierno de 1938. Clotilde intenta evitar que su
        hijo sea enviado a Moscu mientras la guerra se derrumba."
      }
    </script>
  </head>
  <body>
    <p>ISBN 9788401027970</p>
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
        limit: int = 5,
    ) -> list[str]:
        self.queries.append((query, allowed_domains))
        return self.links[:limit]


class StubPageFetcher:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    def fetch_text(self, url: str) -> str | None:
        return self.pages.get(url)


def test_publisher_discovery_finds_publisher_page_without_editorial(tmp_path) -> None:
    fetch_results = [
        FetchResult(
            isbn="9788401027970",
            record=SourceBookRecord(
                source_name="google_books + bne",
                isbn="9788401027970",
                title="El nino que perdio la guerra",
                author="Julia Navarro Coll",
                synopsis='"Madrid, invierno de 1938.',
                categories=['821.134.2-31"19"'],
                language="es",
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    searcher = StubSearcher(
        ["https://www.penguinlibros.com/es/narrativa/123456-el-nino-que-perdio-la-guerra"]
    )
    page_fetcher = StubPageFetcher(
        {
            (
                "https://www.penguinlibros.com/es/narrativa/"
                "123456-el-nino-que-perdio-la-guerra"
            ): PENGUIN_HTML
        }
    )
    cache = FetchResultCache(tmp_path, PUBLISHER_DISCOVERY_CACHE_KEY)

    augmented = augment_fetch_results_with_publisher_discovery(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=page_fetcher,
        cache=cache,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.synopsis.startswith("Madrid, invierno de 1938.")
    assert augmented[0].record.field_sources["synopsis"] == "publisher_page:penguin_random_house"
    assert "publisher_page:penguin_random_house" in augmented[0].record.source_name
    assert searcher.queries
