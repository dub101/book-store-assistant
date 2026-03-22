import httpx

from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.publisher_pages import (
    PUBLISHER_PAGE_ISBN_MISMATCH,
    apply_publisher_page_record,
    augment_fetch_results_with_publisher_pages,
    build_publisher_search_query,
    extract_publisher_page_record,
    match_publisher_profile,
)
from book_store_assistant.sources.results import FetchResult

PLANETA_HTML = """
<html lang="es">
  <head>
    <title>El libro de prueba | Planeta de Libros</title>
    <meta property="og:title" content="El libro de prueba" />
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": "El libro de prueba",
        "isbn": "9780306406157",
        "author": [{"@type": "Person", "name": "Autora Ejemplo"}],
        "publisher": {"@type": "Organization", "name": "Planeta"}
      }
    </script>
  </head>
  <body>
    <section class="book-data">
      <p>Editorial | Planeta</p>
      <p>ISBN | 9780306406157</p>
    </section>
  </body>
</html>
"""

BAD_HTML = """
<html>
  <head><title>Bad page</title></head>
  <body><p>ISBN 9780306406158</p></body>
</html>
"""


class StubSearcher:
    def __init__(self, links: list[str]) -> None:
        self.links = links

    def search(self, query: str, allowed_domains: tuple[str, ...], limit: int = 3) -> list[str]:
        return self.links[:limit]


class StubPageFetcher:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    def fetch_text(self, url: str) -> str | None:
        return self.pages.get(url)


class RaisingSearcher:
    def search(self, query: str, allowed_domains: tuple[str, ...], limit: int = 3) -> list[str]:
        raise httpx.TimeoutException("search timed out")


def test_match_publisher_profile_supports_planeta_imprints() -> None:
    profile = match_publisher_profile("Austral")
    assert profile is not None
    assert profile.key == "planeta"


def test_match_publisher_profile_supports_missing_planeta_aliases() -> None:
    for editorial in (
        "GeoPlaneta",
        "Editorial Ariel",
        "Ediciones Paidós",
        "Planeta Cómic",
        "Gestión 2000",
        "Planeta Audio",
        "Ediciones Temas de Hoy",
        "Lunwerg Editores",
    ):
        profile = match_publisher_profile(editorial)
        assert profile is not None
        assert profile.key == "planeta"


def test_build_publisher_search_query_uses_exact_isbn() -> None:
    query = build_publisher_search_query(
        SourceBookRecord(
            source_name="google_books",
            isbn="9780306406157",
            title="El libro de prueba",
            editorial="Planeta",
        )
    )
    assert '"9780306406157"' in query


def test_extract_publisher_page_record_parses_bibliographic_fields() -> None:
    profile = match_publisher_profile("Planeta")
    assert profile is not None
    record = extract_publisher_page_record(
        PLANETA_HTML,
        "https://www.planetadelibros.com/libro/123",
        "9780306406157",
        profile,
    )

    assert record is not None
    assert record.title == "El libro de prueba"
    assert record.author == "Autora Ejemplo"
    assert record.editorial == "Planeta"


def test_apply_publisher_page_record_fills_missing_author() -> None:
    existing = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        title="El libro de prueba",
        editorial="Planeta",
    )
    publisher = SourceBookRecord(
        source_name="publisher_page:planeta",
        isbn="9780306406157",
        author="Autora Ejemplo",
        editorial="Planeta",
    )

    merged = apply_publisher_page_record(existing, publisher)
    assert merged.author == "Autora Ejemplo"


def test_augment_fetch_results_with_publisher_pages_fills_missing_author() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="El libro de prueba",
                editorial="Planeta",
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    searcher = StubSearcher(["https://www.planetadelibros.com/libro/123"])
    page_fetcher = StubPageFetcher({"https://www.planetadelibros.com/libro/123": PLANETA_HTML})

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=page_fetcher,
        max_retries=0,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.author == "Autora Ejemplo"


def test_augment_fetch_results_with_publisher_pages_records_issue_codes_on_failure() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="El libro de prueba",
                editorial="Planeta",
            ),
            errors=[],
            issue_codes=[],
        )
    ]

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=RaisingSearcher(),
        page_fetcher=StubPageFetcher({}),
        max_retries=0,
    )

    assert augmented[0].record is not None
    assert "PUBLISHER_PAGE_SEARCH_TIMEOUT" in augmented[0].issue_codes
    assert PUBLISHER_PAGE_ISBN_MISMATCH not in augmented[0].issue_codes
