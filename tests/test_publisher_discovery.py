from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.publisher_discovery import (
    augment_fetch_results_with_publisher_discovery,
    build_publisher_discovery_search_queries,
)
from book_store_assistant.sources.results import FetchResult

PENGUIN_HTML = """
<html lang="es">
  <head>
    <title>El nino que perdio la guerra | Penguin Libros</title>
    <meta property="og:title" content="El nino que perdio la guerra" />
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": "El nino que perdio la guerra",
        "isbn": "9788401027970",
        "author": [{"@type": "Person", "name": "Julia Navarro"}],
        "publisher": {"@type": "Organization", "name": "Plaza & Janes"}
      }
    </script>
    <meta property="og:description" content="Madrid, invierno de 1938." />
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

    def search(self, query: str, allowed_domains: tuple[str, ...], limit: int = 5) -> list[str]:
        self.queries.append((query, allowed_domains))
        return self.links[:limit]


class StubPageFetcher:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    def fetch_text(self, url: str) -> str | None:
        return self.pages.get(url)


def test_publisher_discovery_finds_bibliographic_fields_without_editorial() -> None:
    fetch_results = [
        FetchResult(
            isbn="9788401027970",
            record=SourceBookRecord(
                source_name="google_books + bne",
                isbn="9788401027970",
                title="El nino que perdio la guerra",
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

    augmented = augment_fetch_results_with_publisher_discovery(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=page_fetcher,
        max_retries=0,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.author == "Julia Navarro"
    assert augmented[0].record.editorial == "Plaza & Janes"
    assert searcher.queries[0][0] == '"9788401027970" "El nino que perdio la guerra"'


def test_publisher_discovery_queries_use_collected_record_context() -> None:
    assert build_publisher_discovery_search_queries(
        SourceBookRecord(
            source_name="google_books + bne",
            isbn="9788401027970",
            title="El nino que perdio la guerra [Texto impreso]",
            author="Julia Navarro",
            editorial="Barcelona, Plaza & Janes",
        )
    ) == [
        '"9788401027970" "El nino que perdio la guerra" "Julia Navarro"',
        '"9788401027970"',
    ]


def test_publisher_discovery_recovers_from_fetch_error() -> None:
    fetch_results = [
        FetchResult(
            isbn="9788401027970",
            record=None,
            errors=["google_books: No Google Books match found."],
            issue_codes=["GOOGLE_BOOKS:GOOGLE_BOOKS_NO_MATCH"],
        )
    ]
    page_url = "https://www.penguinlibros.com/es/narrativa/123456-el-nino-que-perdio-la-guerra"
    searcher = StubSearcher([page_url])
    page_fetcher = StubPageFetcher({page_url: PENGUIN_HTML})

    augmented = augment_fetch_results_with_publisher_discovery(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=page_fetcher,
        max_retries=0,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.title == "El nino que perdio la guerra"
    assert augmented[0].record.author == "Julia Navarro"
    assert augmented[0].record.editorial == "Plaza & Janes"
