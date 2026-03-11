from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.publisher_pages import (
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
    <meta property="og:image" content="https://www.planetadelibros.com/cover.jpg" />
    <meta
      property="og:description"
      content="Una novela sobre memoria y secretos.
      Una ciudad costera atraviesa varias generaciones."
    />
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": "El libro de prueba",
        "isbn": "9780306406157",
        "author": [{"@type": "Person", "name": "Autora Ejemplo"}],
        "publisher": {"@type": "Organization", "name": "Planeta"},
        "description": "Una novela sobre memoria y secretos. Una ciudad costera deja huella.",
        "image": "https://www.planetadelibros.com/cover.jpg"
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

    def fetch_text(self, url: str) -> str | None:
        return self.pages.get(url)


def test_match_publisher_profile_supports_planeta_imprints() -> None:
    profile = match_publisher_profile("Austral")

    assert profile is not None
    assert profile.key == "planeta"
    assert profile.domains == ("planetadelibros.com",)


def test_build_publisher_search_query_uses_isbn_title_and_primary_author() -> None:
    query = build_publisher_search_query(
        SourceBookRecord(
            source_name="google_books",
            isbn="9780306406157",
            title="El libro de prueba",
            author="Autora Ejemplo, Otra Autora",
        )
    )

    assert query == '"9780306406157" "El libro de prueba" "Autora Ejemplo"'


def test_extract_publisher_page_record_parses_book_metadata_from_html() -> None:
    profile = match_publisher_profile("Planeta")
    assert profile is not None

    record = extract_publisher_page_record(
        PLANETA_HTML,
        "https://www.planetadelibros.com/libro-de-prueba/123456",
        "9780306406157",
        profile,
    )

    assert record is not None
    assert record.source_name == "publisher_page:planeta"
    assert str(record.source_url) == "https://www.planetadelibros.com/libro-de-prueba/123456"
    assert record.title == "El libro de prueba"
    assert record.author == "Autora Ejemplo"
    assert record.editorial == "Planeta"
    assert record.synopsis == (
        "Una novela sobre memoria y secretos. Una ciudad costera deja huella."
    )
    assert record.language == "es"
    assert str(record.cover_url) == "https://www.planetadelibros.com/cover.jpg"


def test_apply_publisher_page_record_prefers_official_source_url_and_spanish_synopsis() -> None:
    existing = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        source_url="https://books.google.com/books?id=abc123",
        title="El libro de prueba",
        author="Autora Ejemplo",
        editorial="Planeta",
        synopsis="Detailed English description from a non-official source.",
        language="en",
        field_sources={
            "title": "google_books",
            "author": "google_books",
            "editorial": "google_books",
            "synopsis": "google_books",
            "language": "google_books",
            "source_url": "google_books",
        },
    )
    publisher = SourceBookRecord(
        source_name="publisher_page:planeta",
        isbn="9780306406157",
        source_url="https://www.planetadelibros.com/libro-de-prueba/123456",
        synopsis="Sinopsis oficial en espanol del libro de prueba.",
        language="es",
    )

    merged = apply_publisher_page_record(existing, publisher)

    assert merged.synopsis == "Sinopsis oficial en espanol del libro de prueba."
    assert merged.language == "es"
    assert str(merged.source_url) == "https://www.planetadelibros.com/libro-de-prueba/123456"
    assert merged.field_sources["synopsis"] == "publisher_page:planeta"
    assert merged.field_sources["language"] == "publisher_page:planeta"
    assert merged.field_sources["source_url"] == "publisher_page:planeta"


def test_augment_fetch_results_with_publisher_pages_updates_supported_publishers() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="El libro de prueba",
                author="Autora Ejemplo",
                editorial="Planeta",
                language="en",
            ),
            errors=[],
        )
    ]
    searcher = StubSearcher(
        ["https://www.planetadelibros.com/libro-de-prueba/123456"]
    )
    page_fetcher = StubPageFetcher(
        {"https://www.planetadelibros.com/libro-de-prueba/123456": PLANETA_HTML}
    )

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=page_fetcher,
    )

    assert len(augmented) == 1
    assert augmented[0].record is not None
    assert augmented[0].record.synopsis is not None
    assert augmented[0].record.language == "es"
    assert "planetadelibros.com" in str(augmented[0].record.source_url)
    assert searcher.queries == [
        (
            '"9780306406157" "El libro de prueba" "Autora Ejemplo"',
            ("planetadelibros.com",),
        )
    ]


def test_augment_fetch_results_with_publisher_pages_skips_unsupported_publishers() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="El libro de prueba",
                author="Autora Ejemplo",
                editorial="Editorial Desconocida",
            ),
            errors=[],
        )
    ]
    searcher = StubSearcher(["https://www.example.com/book"])

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=StubPageFetcher({}),
    )

    assert augmented == fetch_results
    assert searcher.queries == []
