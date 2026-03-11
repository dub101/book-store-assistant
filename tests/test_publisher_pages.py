import httpx

from book_store_assistant.sources.cache import FetchResultCache
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


class RaisingSearcher:
    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = 3,
    ) -> list[str]:
        raise httpx.TimeoutException("search timed out")


def test_match_publisher_profile_supports_planeta_imprints() -> None:
    profile = match_publisher_profile("Austral")

    assert profile is not None
    assert profile.key == "planeta"
    assert profile.domains == ("planetadelibros.com",)


def test_match_publisher_profile_supports_penguin_random_house_imprints() -> None:
    profile = match_publisher_profile("Alfaguara")

    assert profile is not None
    assert profile.key == "penguin_random_house"
    assert profile.domains == ("penguinlibros.com", "megustaleer.com")


def test_match_publisher_profile_supports_composite_editorial_strings() -> None:
    profile = match_publisher_profile(
        (
            "Alfaguara, Real Academia Española, "
            "Asociación de Academias de la Lengua Española"
        )
    )

    assert profile is not None
    assert profile.key == "penguin_random_house"

    profile = match_publisher_profile("Real Academia Española / Alfaguara")

    assert profile is not None
    assert profile.key == "penguin_random_house"


def test_match_publisher_profile_supports_anagrama() -> None:
    profile = match_publisher_profile("Editorial Anagrama")

    assert profile is not None
    assert profile.key == "anagrama"
    assert profile.domains == ("anagrama-ed.es",)


def test_match_publisher_profile_supports_urano_imprints() -> None:
    profile = match_publisher_profile("Umbriel")

    assert profile is not None
    assert profile.key == "urano"
    assert profile.domains == ("edicionesurano.com",)


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


def test_extract_publisher_page_record_requires_matching_isbn_on_page() -> None:
    profile = match_publisher_profile("Planeta")
    assert profile is not None

    html_without_isbn = """
    <html lang="es">
      <head>
        <title>El libro de prueba | Planeta de Libros</title>
        <meta property="og:title" content="El libro de prueba" />
        <meta property="og:description" content="Una novela sobre memoria y secretos." />
      </head>
      <body>
        <p>Editorial | Planeta</p>
      </body>
    </html>
    """

    record = extract_publisher_page_record(
        html_without_isbn,
        "https://www.planetadelibros.com/libro-de-prueba/123456",
        "9780306406157",
        profile,
    )

    assert record is None


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


def test_publisher_pages_skips_lookup_for_records_with_complete_metadata() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="El libro de prueba",
                author="Autora Ejemplo",
                editorial="Planeta",
                synopsis="Sinopsis oficial en espanol del libro de prueba.",
                language="es",
                subject="FICCION",
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    searcher = StubSearcher(["https://www.planetadelibros.com/libro-de-prueba/123456"])

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=StubPageFetcher({}),
    )

    assert augmented == fetch_results
    assert searcher.queries == []


def test_publisher_pages_discovers_supported_publishers_when_editorial_is_missing() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="open_library",
                isbn="9780306406157",
                title="El libro de prueba",
                author="Autora Ejemplo",
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
    assert augmented[0].record.editorial == "Planeta"
    assert augmented[0].record.synopsis is not None
    assert augmented[0].record.language == "es"
    assert searcher.queries == [
        (
            '"9780306406157" "El libro de prueba" "Autora Ejemplo"',
            ("penguinlibros.com", "megustaleer.com"),
        ),
        (
            '"9780306406157" "El libro de prueba" "Autora Ejemplo"',
            ("planetadelibros.com",),
        ),
    ]


def test_publisher_pages_falls_back_to_discovery_for_unknown_editorials() -> None:
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


def test_publisher_pages_records_search_timeout_issue_codes() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="open_library",
                isbn="9780306406157",
                title="El libro de prueba",
                author="Autora Ejemplo",
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
    )

    assert augmented[0].issue_codes == [
        "PUBLISHER_PAGE_SEARCH_TIMEOUT",
        "PUBLISHER_PAGE_NO_MATCH",
    ]


def test_publisher_pages_records_isbn_mismatch_issue_code() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9780306406157",
                title="El libro de prueba",
                author="Autora Ejemplo",
                editorial="Planeta",
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    searcher = StubSearcher(["https://www.planetadelibros.com/libro-de-prueba/123456"])
    page_fetcher = StubPageFetcher(
        {
            "https://www.planetadelibros.com/libro-de-prueba/123456": """
            <html><body><p>ISBN | 9780306406158</p></body></html>
            """
        }
    )

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=page_fetcher,
    )

    assert augmented[0].issue_codes == [
        PUBLISHER_PAGE_ISBN_MISMATCH,
        "PUBLISHER_PAGE_NO_MATCH",
    ]


def test_publisher_pages_reuses_cached_confirmed_match_without_searching(tmp_path) -> None:
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
            issue_codes=[],
        )
    ]
    cache = FetchResultCache(tmp_path / "publisher-cache", "publisher_page_lookup_v1")
    cache.set(
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="publisher_page:planeta",
                isbn="9780306406157",
                source_url="https://www.planetadelibros.com/libro-de-prueba/123456",
                synopsis="Sinopsis oficial en espanol del libro de prueba.",
                language="es",
            ),
            errors=[],
            issue_codes=[],
        )
    )
    searcher = StubSearcher(["https://www.planetadelibros.com/libro-de-prueba/123456"])

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=StubPageFetcher({}),
        cache=cache,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.synopsis == "Sinopsis oficial en espanol del libro de prueba."
    assert searcher.queries == []
