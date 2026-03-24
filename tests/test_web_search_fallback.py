from book_store_assistant.bibliographic.evidence import (
    WebSearchBibliographicExtraction,
)
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.search_queries import (
    build_editorial_discovery_queries,
)
from book_store_assistant.sources.web_search import (
    _search_domain_groups,
    augment_fetch_results_with_editorial_search,
    augment_fetch_results_with_web_search,
)


class StubSearcher:
    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = 5,
    ) -> list[str]:
        del query, allowed_domains, limit
        return ["https://www.planetadelibros.com/libro/ejemplo/123"]


class ContextualSearcher:
    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = 5,
    ) -> list[str]:
        del query, allowed_domains, limit
        return ["https://www.penguinlibros.com/es/narrativa/123-en-agosto-nos-vemos"]


class StubPageFetcher:
    def fetch_text(self, url: str) -> str | None:
        del url
        return """
        <html>
          <head><title>Historia de Espana</title></head>
          <body>
            <p>ISBN 9780306406157</p>
            <p>Historia de Espana</p>
            <p>Fernando Garcia de Cortazar</p>
            <p>Planeta</p>
          </body>
        </html>
        """


class ContextualPageFetcher:
    def fetch_text(self, url: str) -> str | None:
        del url
        return """
        <html>
          <head><title>En agosto nos vemos | Penguin Libros</title></head>
          <body>
            <p>En agosto nos vemos</p>
            <p>Gabriel Garcia Marquez</p>
            <p>Random House</p>
          </body>
        </html>
        """


class StubExtractor:
    def extract(self, source_record, evidence_documents):
        assert source_record.isbn == "9780306406157"
        assert evidence_documents
        return WebSearchBibliographicExtraction(
            confidence=0.96,
            title="Historia de Espana",
            subtitle=None,
            author="Fernando Garcia de Cortazar",
            editorial="Planeta",
            publisher="Planeta",
            support={
                "title": [0],
                "subtitle": [],
                "author": [0],
                "editorial": [0],
                "publisher": [0],
            },
            issues=[],
            explanation="Grounded in the official publisher page.",
        )


class LowConfidenceExtractor:
    def extract(self, source_record, evidence_documents):
        del source_record, evidence_documents
        return WebSearchBibliographicExtraction(
            confidence=0.6,
            title="Historia de Espana",
            subtitle=None,
            author="Fernando Garcia de Cortazar",
            editorial="Planeta",
            publisher="Planeta",
            support={
                "title": [0],
                "subtitle": [],
                "author": [0],
                "editorial": [0],
                "publisher": [0],
            },
            issues=["extractor_low_confidence"],
            explanation="Low confidence.",
        )


class UnexpectedSearcher:
    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = 5,
    ) -> list[str]:
        del query, allowed_domains, limit
        raise AssertionError("web search should not run")


class ContextualExtractor:
    def extract(self, source_record, evidence_documents):
        assert source_record.isbn == "9788439743071"
        assert evidence_documents
        assert evidence_documents[0].isbn_present is False
        return WebSearchBibliographicExtraction(
            confidence=0.94,
            title="En agosto nos vemos",
            subtitle=None,
            author="Gabriel Garcia Marquez",
            editorial="Random House",
            publisher="Penguin Random House",
            support={
                "title": [0],
                "subtitle": [],
                "author": [0],
                "editorial": [0],
                "publisher": [0],
            },
            issues=[],
            explanation="Grounded in the official publisher page title and body text.",
        )


def test_web_search_fallback_fills_missing_fields_and_cleans_catalog_values() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="bne",
                isbn="9780306406157",
                title="Historia de Espana [Texto impreso]",
                author=None,
                editorial="Barcelona, Planeta",
            ),
            errors=[],
            issue_codes=[],
        )
    ]

    augmented = augment_fetch_results_with_web_search(
        fetch_results,
        timeout_seconds=5.0,
        extractor=StubExtractor(),
        searcher=StubSearcher(),
        page_fetcher=StubPageFetcher(),
        max_pages_per_record=1,
        max_search_attempts_per_record=1,
        max_fetch_attempts_per_record=1,
    )

    assert augmented[0].record is not None
    assert augmented[0].record.title == "Historia de Espana"
    assert augmented[0].record.author == "Fernando Garcia de Cortazar"
    assert augmented[0].record.editorial == "Planeta"
    assert str(augmented[0].record.source_url) == "https://www.planetadelibros.com/libro/ejemplo/123"
    assert augmented[0].record.raw_source_payload is not None


def test_web_search_fallback_records_issue_when_extraction_is_low_confidence() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="bne",
                isbn="9780306406157",
                title="Historia de Espana [Texto impreso]",
                author=None,
                editorial="Barcelona, Planeta",
            ),
            errors=[],
            issue_codes=[],
        )
    ]

    augmented = augment_fetch_results_with_web_search(
        fetch_results,
        timeout_seconds=5.0,
        extractor=LowConfidenceExtractor(),
        searcher=StubSearcher(),
        page_fetcher=StubPageFetcher(),
        max_pages_per_record=1,
        max_search_attempts_per_record=1,
        max_fetch_attempts_per_record=1,
    )

    assert augmented[0].record is not None
    assert "WEB_SEARCH_EXTRACTION_UNAVAILABLE" in augmented[0].issue_codes


def test_editorial_search_skips_records_that_already_have_editorial() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="bne",
                isbn="9780306406157",
                title="Historia de Espana",
                author="Fernando Garcia de Cortazar",
                editorial="Barcelona, Planeta",
            ),
            errors=[],
            issue_codes=[],
        )
    ]

    augmented = augment_fetch_results_with_editorial_search(
        fetch_results,
        timeout_seconds=5.0,
        extractor=StubExtractor(),
        searcher=UnexpectedSearcher(),
        page_fetcher=StubPageFetcher(),
        max_pages_per_record=1,
        max_search_attempts_per_record=1,
        max_fetch_attempts_per_record=1,
    )

    assert augmented == fetch_results


def test_web_search_preliminary_stage_accepts_contextual_official_pages_without_isbn() -> None:
    fetch_results = [
        FetchResult(
            isbn="9788439743071",
            record=SourceBookRecord(
                source_name="google_books",
                isbn="9788439743071",
                title="En agosto nos vemos",
                author="Gabriel Garcia Marquez",
            ),
            errors=[],
            issue_codes=[],
        )
    ]

    augmented = augment_fetch_results_with_web_search(
        fetch_results,
        timeout_seconds=5.0,
        extractor=ContextualExtractor(),
        searcher=ContextualSearcher(),
        page_fetcher=ContextualPageFetcher(),
        max_pages_per_record=1,
        max_search_attempts_per_record=10,
        max_fetch_attempts_per_record=1,
        allow_contextual_matches=True,
        status_label="preliminary",
    )

    assert augmented[0].record is not None
    assert augmented[0].record.editorial == "Random House"
    assert (
        str(augmented[0].record.source_url)
        == "https://www.penguinlibros.com/es/narrativa/123-en-agosto-nos-vemos"
    )
    assert augmented[0].record.raw_source_payload is not None


def test_editorial_search_queries_use_collected_record_context() -> None:
    queries = build_editorial_discovery_queries(
        SourceBookRecord(
            source_name="bne",
            isbn="9780306406157",
            title="Historia de Espana [Texto impreso]",
            subtitle="Una breve historia visual",
            author="Fernando Garcia de Cortazar",
            editorial="Barcelona, Editorial Ariel",
        )
    )

    assert queries
    assert queries[0] == (
        "Editorial del libro con isbn 9780306406157 "
        "y informacion extra: titulo Historia de Espana; "
        "subtitulo Una breve historia visual; autor Fernando Garcia de Cortazar"
    )
    assert queries[1] == '"9780306406157" "editorial"'
    assert queries[2] == '"9780306406157" "Historia de Espana"'
    assert queries[4] == (
        '"9780306406157" "Historia de Espana" "Fernando Garcia de Cortazar"'
    )
    assert '"9780306406157" "Una breve historia visual"' in queries


def test_web_search_domain_groups_prioritize_publisher_domains() -> None:
    groups = _search_domain_groups(
        SourceBookRecord(
            source_name="bne",
            isbn="9780306406157",
            title="Historia de Espana",
        )
    )

    assert groups[0] == (
        "penguinlibros.com",
        "megustaleer.com",
        "planetadelibros.com",
        "anagrama-ed.es",
    )
    assert groups[1] == (
        "agapea.com",
        "buscalibre.com",
        "buscalibre.cl",
        "buscalibre.com.co",
    )


class RecordingSearcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = 5,
    ) -> list[str]:
        del limit
        self.calls.append((query, allowed_domains))
        return []


def test_web_search_attempt_plan_uses_isbn_query_early() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(
                source_name="bne",
                isbn="9780306406157",
                title="Historia de Espana [Texto impreso]",
                author=None,
                editorial=None,
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    searcher = RecordingSearcher()

    augment_fetch_results_with_editorial_search(
        fetch_results,
        timeout_seconds=5.0,
        extractor=StubExtractor(),
        searcher=searcher,
        page_fetcher=StubPageFetcher(),
        max_pages_per_record=1,
        max_search_attempts_per_record=4,
        max_fetch_attempts_per_record=1,
    )

    assert [call[0] for call in searcher.calls] == [
        "Editorial del libro con isbn 9780306406157 y informacion extra: titulo Historia de Espana",
        '"9780306406157" "editorial"',
        '"9780306406157" "Historia de Espana"',
        "Editorial del libro con isbn 9780306406157 y informacion extra: titulo Historia de Espana",
    ]
    assert all(call[1] != () for call in searcher.calls)
    assert searcher.calls[0][1] == (
        "penguinlibros.com",
        "megustaleer.com",
        "planetadelibros.com",
        "anagrama-ed.es",
    )
