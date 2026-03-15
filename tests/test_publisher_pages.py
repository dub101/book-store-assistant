import httpx

from book_store_assistant.sources.cache import FetchResultCache
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.publisher_pages import (
    PUBLISHER_PAGE_ISBN_MISMATCH,
    _rank_candidate_urls,
    apply_publisher_page_record,
    augment_fetch_results_with_publisher_pages,
    build_publisher_search_queries,
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


class FlakySearcher:
    def __init__(self, links: list[str], failures: int, status_code: int = 503) -> None:
        self.links = links
        self.failures = failures
        self.status_code = status_code
        self.calls = 0

    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = 3,
    ) -> list[str]:
        self.calls += 1
        if self.calls <= self.failures:
            request = httpx.Request("GET", "https://html.duckduckgo.com/html/")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                f"search failed with {self.status_code}",
                request=request,
                response=response,
            )
        return self.links[:limit]


class FlakyPageFetcher:
    def __init__(self, pages: dict[str, str], failures: int, status_code: int = 503) -> None:
        self.pages = pages
        self.failures = failures
        self.status_code = status_code
        self.calls = 0

    def fetch_text(self, url: str) -> str | None:
        self.calls += 1
        if self.calls <= self.failures:
            request = httpx.Request("GET", url)
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                f"fetch failed with {self.status_code}",
                request=request,
                response=response,
            )
        return self.pages.get(url)


class RaisingSearcher:
    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = 3,
    ) -> list[str]:
        raise httpx.TimeoutException("search timed out")


class QueryAwareSearcher:
    def __init__(
        self,
        expected_domain: str,
        expected_query_fragment: str,
        links: list[str],
    ) -> None:
        self.expected_domain = expected_domain
        self.expected_query_fragment = expected_query_fragment.casefold()
        self.links = links
        self.queries: list[tuple[str, tuple[str, ...]]] = []

    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = 3,
    ) -> list[str]:
        self.queries.append((query, allowed_domains))
        if (
            self.expected_domain in allowed_domains
            and self.expected_query_fragment in query.casefold()
        ):
            return self.links[:limit]
        return []


def test_match_publisher_profile_supports_planeta_imprints() -> None:
    profile = match_publisher_profile("Austral")

    assert profile is not None
    assert profile.key == "planeta"
    assert profile.domains == ("planetadelibros.com",)

    profile = match_publisher_profile("Grupo Planeta (GBS)")

    assert profile is not None
    assert profile.key == "planeta"

    profile = match_publisher_profile("[Barcelona], Deusto")

    assert profile is not None
    assert profile.key == "planeta"

    profile = match_publisher_profile("Destino Infantil & Juvenil")

    assert profile is not None
    assert profile.key == "planeta"


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

    profile = match_publisher_profile("Real Academia Espanola")

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


def test_match_publisher_profile_supports_galaxia_gutenberg() -> None:
    profile = match_publisher_profile("Barcelona, Círculo de Lectores, Galaxia Gutenberg")

    assert profile is not None
    assert profile.key == "galaxia_gutenberg"
    assert profile.domains == ("galaxiagutenberg.com",)


def test_match_publisher_profile_supports_norma_editorial() -> None:
    profile = match_publisher_profile("Norma S A Editorial")

    assert profile is not None
    assert profile.key == "norma_editorial"
    assert profile.domains == ("normaeditorial.com",)


def test_match_publisher_profile_supports_lectorum() -> None:
    profile = match_publisher_profile("Lectorum Publications")

    assert profile is not None
    assert profile.key == "lectorum"
    assert profile.domains == ("lectorum.com",)


def test_match_publisher_profile_supports_harpercollins_iberica() -> None:
    profile = match_publisher_profile("HarperCollins Ibérica")

    assert profile is not None
    assert profile.key == "harpercollins_iberica"
    assert profile.domains == ("harpercollinsiberica.com",)


def test_match_publisher_profile_supports_grupo_anaya_imprints() -> None:
    profile = match_publisher_profile("Alianza Editorial")

    assert profile is not None
    assert profile.key == "grupo_anaya"
    assert profile.domains == ("anaya.es", "anayainfantilyjuvenil.com")

    profile = match_publisher_profile("Cátedra")

    assert profile is not None
    assert profile.key == "grupo_anaya"


def test_match_publisher_profile_supports_rba() -> None:
    profile = match_publisher_profile("RBA Libros")

    assert profile is not None
    assert profile.key == "rba"
    assert profile.domains == ("rbalibros.com",)


def test_match_publisher_profile_supports_oceano() -> None:
    profile = match_publisher_profile("Océano Gran Travesía")

    assert profile is not None
    assert profile.key == "oceano"
    assert profile.domains == ("oceano.com",)


def test_match_publisher_profile_supports_sm_imprints() -> None:
    profile = match_publisher_profile("Ediciones SM")

    assert profile is not None
    assert profile.key == "sm"
    assert profile.domains == ("grupo-sm.com", "literaturasm.com")

    profile = match_publisher_profile("El Barco de Vapor")

    assert profile is not None
    assert profile.key == "sm"


def test_match_publisher_profile_supports_new_trade_and_childrens_publishers() -> None:
    cases = [
        ("Kalandraka", "kalandraka", ("kalandraka.com",)),
        ("Combel Editorial", "combel", ("combeleditorial.com",)),
        ("Nórdica Libros", "nordica", ("nordicalibros.com",)),
        ("Libros del Asteroide", "libros_del_asteroide", ("librosdelasteroide.com",)),
        ("Editorial Flamboyant", "flamboyant", ("editorialflamboyant.com",)),
        ("Libros del Zorro Rojo", "zorro_rojo", ("librosdelzorrorojo.com",)),
        ("Editorial Siruela", "siruela", ("siruela.com",)),
    ]

    for editorial, expected_key, expected_domains in cases:
        profile = match_publisher_profile(editorial)

        assert profile is not None
        assert profile.key == expected_key
        assert profile.domains == expected_domains


def test_match_publisher_profile_supports_lookup_dictionary_aliases() -> None:
    profile = match_publisher_profile("Ediciones Destino")

    assert profile is not None
    assert profile.key == "planeta"

    profile = match_publisher_profile("Plaza y Janes")

    assert profile is not None
    assert profile.key == "penguin_random_house"


def test_build_publisher_search_query_uses_isbn_title_and_primary_author() -> None:
    query = build_publisher_search_query(
        SourceBookRecord(
            source_name="google_books",
            isbn="9780306406157",
            title="El libro de prueba: edición especial",
            author="Autora Ejemplo, Otra Autora",
            editorial="Planeta",
        )
    )

    assert query == '"9780306406157"'


def test_build_publisher_search_queries_are_exact_isbn_only() -> None:
    profile = match_publisher_profile("Planeta")
    assert profile is not None

    queries = build_publisher_search_queries(
        SourceBookRecord(
            source_name="google_books",
            isbn="9780306406157",
            title="El libro de prueba",
            author="Autora Ejemplo, Otra Autora",
        ),
        profile=profile,
    )

    assert queries == ['"9780306406157"']


def test_rank_candidate_urls_prefers_exact_isbn_urls() -> None:
    record = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        title="El libro de prueba",
        author="Autora Ejemplo",
    )

    ranked = _rank_candidate_urls(
        [
            "https://www.planetadelibros.com/autor/autora-ejemplo/00001",
            "https://www.planetadelibros.com/libro/9780306406157/123456",
            "https://www.planetadelibros.com/blog/noticias-del-mes/99999",
        ],
        record,
    )

    assert ranked[0] == "https://www.planetadelibros.com/libro/9780306406157/123456"


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
            '"9780306406157"',
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


def test_publisher_pages_skips_lookup_when_editorial_is_missing() -> None:
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
    searcher = StubSearcher(["https://www.planetadelibros.com/libro-de-prueba/123456"])

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=StubPageFetcher({}),
    )

    assert len(augmented) == 1
    assert augmented[0].record is not None
    assert augmented[0].record.editorial is None
    assert searcher.queries == []


def test_publisher_pages_uses_editorial_hint_for_known_publishers() -> None:
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
    searcher = QueryAwareSearcher(
        expected_domain="planetadelibros.com",
        expected_query_fragment='"9780306406157"',
        links=["https://www.planetadelibros.com/libro-de-prueba/123456"],
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

    assert augmented[0].record is not None
    assert augmented[0].record.editorial == "Planeta"
    assert any(
        query == '"9780306406157"' and "planetadelibros.com" in domains[0]
        for query, domains in searcher.queries
    )


def test_publisher_pages_tries_best_ranked_candidate_first() -> None:
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
        [
            "https://www.planetadelibros.com/blog/noticias-del-mes/99999",
            "https://www.planetadelibros.com/libro/el-libro-de-prueba/123456",
        ]
    )
    page_fetcher = StubPageFetcher(
        {
            "https://www.planetadelibros.com/blog/noticias-del-mes/99999": "<html></html>",
            "https://www.planetadelibros.com/libro/el-libro-de-prueba/123456": PLANETA_HTML,
        }
    )

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=page_fetcher,
    )

    assert augmented[0].record is not None
    assert "planetadelibros.com" in str(augmented[0].record.source_url)


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


def test_publisher_pages_honors_profile_and_search_budgets() -> None:
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
    searcher = StubSearcher([])

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=StubPageFetcher({}),
        max_retries=0,
        max_profiles_per_record=1,
        max_search_attempts_per_record=1,
    )

    assert augmented[0].issue_codes == ["PUBLISHER_PAGE_NO_MATCH"]
    assert len(searcher.queries) == 1


def test_publisher_pages_honors_fetch_budget() -> None:
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
    searcher = StubSearcher(["https://www.planetadelibros.com/libro-de-prueba/123456"])
    page_fetcher = StubPageFetcher(
        {"https://www.planetadelibros.com/libro-de-prueba/123456": PLANETA_HTML}
    )

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=page_fetcher,
        max_retries=0,
        max_fetch_attempts_per_record=0,
    )

    assert augmented[0].issue_codes == [
        "PUBLISHER_PAGE_FETCH_BUDGET_EXHAUSTED",
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
        cache_ttl_seconds=0,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.synopsis == "Sinopsis oficial en espanol del libro de prueba."
    assert searcher.queries == []


def test_publisher_pages_reuses_cached_negative_result_without_searching(tmp_path) -> None:
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
            record=None,
            errors=[],
            issue_codes=["PUBLISHER_PAGE_SEARCH_TIMEOUT", "PUBLISHER_PAGE_NO_MATCH"],
        ),
        allow_empty=True,
    )
    searcher = StubSearcher(["https://www.planetadelibros.com/libro-de-prueba/123456"])

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=StubPageFetcher({}),
        cache=cache,
        cache_ttl_seconds=3600,
    )

    assert augmented[0].record is not None
    assert augmented[0].issue_codes == [
        "PUBLISHER_PAGE_SEARCH_TIMEOUT",
        "PUBLISHER_PAGE_NO_MATCH",
    ]
    assert searcher.queries == []


def test_publisher_pages_retries_after_expired_negative_cache(tmp_path) -> None:
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
            record=None,
            errors=[],
            issue_codes=["PUBLISHER_PAGE_SEARCH_TIMEOUT", "PUBLISHER_PAGE_NO_MATCH"],
        ),
        allow_empty=True,
    )
    cache_path = tmp_path / "publisher-cache" / "9780306406157.json"
    cache_path.write_text(
        cache.get_entry("9780306406157")
        .model_copy(update={"cached_at": 0})
        .model_dump_json(indent=2),
        encoding="utf-8",
    )
    searcher = StubSearcher(["https://www.planetadelibros.com/libro-de-prueba/123456"])

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=StubPageFetcher(
            {"https://www.planetadelibros.com/libro-de-prueba/123456": PLANETA_HTML}
        ),
        cache=cache,
        cache_ttl_seconds=3600,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.synopsis is not None
    assert searcher.queries == [
        (
            '"9780306406157"',
            ("planetadelibros.com",),
        )
    ]


def test_publisher_pages_retries_search_before_succeeding() -> None:
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
    searcher = FlakySearcher(
        ["https://www.planetadelibros.com/libro-de-prueba/123456"],
        failures=1,
    )
    sleep_calls: list[float] = []

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=searcher,
        page_fetcher=StubPageFetcher(
            {"https://www.planetadelibros.com/libro-de-prueba/123456": PLANETA_HTML}
        ),
        max_retries=2,
        backoff_seconds=0.25,
        sleep=sleep_calls.append,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.synopsis is not None
    assert searcher.calls == 2
    assert sleep_calls == [0.25]


def test_publisher_pages_retries_fetch_before_succeeding() -> None:
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
    page_fetcher = FlakyPageFetcher(
        {"https://www.planetadelibros.com/libro-de-prueba/123456": PLANETA_HTML},
        failures=1,
    )
    sleep_calls: list[float] = []

    augmented = augment_fetch_results_with_publisher_pages(
        fetch_results,
        timeout_seconds=1.0,
        searcher=StubSearcher(["https://www.planetadelibros.com/libro-de-prueba/123456"]),
        page_fetcher=page_fetcher,
        max_retries=2,
        backoff_seconds=0.25,
        sleep=sleep_calls.append,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.synopsis is not None
    assert page_fetcher.calls == 2
    assert sleep_calls == [0.25]
