from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.publisher_discovery import (
    augment_fetch_results_with_publisher_discovery,
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

    def search(self, query: str, allowed_domains: tuple[str, ...], limit: int = 5) -> list[str]:
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
