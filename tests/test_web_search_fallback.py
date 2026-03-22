from book_store_assistant.bibliographic.evidence import (
    WebSearchBibliographicExtraction,
)
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.web_search import augment_fetch_results_with_web_search


class StubSearcher:
    def search(
        self,
        query: str,
        allowed_domains: tuple[str, ...],
        limit: int = 5,
    ) -> list[str]:
        del query, allowed_domains, limit
        return ["https://www.planetadelibros.com/libro/ejemplo/123"]


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


def test_web_search_fallback_skips_editorial_cleanup_only_records() -> None:
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

    augmented = augment_fetch_results_with_web_search(
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
