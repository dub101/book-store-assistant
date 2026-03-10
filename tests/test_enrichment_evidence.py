from book_store_assistant.enrichment.evidence import (
    PAGE_DESCRIPTION_EVIDENCE,
    SOURCE_SYNOPSIS_EVIDENCE,
    collect_descriptive_evidence,
)
from book_store_assistant.enrichment.page_fetch import extract_description_from_html
from book_store_assistant.sources.models import SourceBookRecord


class StubPageFetcher:
    def __init__(self, html: str | None) -> None:
        self.html = html

    def fetch_text(self, url: str) -> str | None:
        return self.html


def test_extract_description_from_html_reads_meta_description() -> None:
    html = '<html><head><meta name="description" content="Example description."></head></html>'

    assert extract_description_from_html(html) == "Example description."


def test_collect_descriptive_evidence_uses_source_synopsis_first() -> None:
    record = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        synopsis="Resumen existente.",
        language="es",
    )

    evidence = collect_descriptive_evidence(record, page_fetcher=StubPageFetcher("<html></html>"))

    assert len(evidence) == 1
    assert evidence[0].evidence_type == SOURCE_SYNOPSIS_EVIDENCE


def test_collect_descriptive_evidence_uses_page_description_when_synopsis_missing() -> None:
    record = SourceBookRecord(
        source_name="open_library",
        isbn="9780306406157",
        source_url="https://openlibrary.org/books/OL1M/Example-Title",
        language="en",
        field_sources={"source_url": "open_library"},
    )

    evidence = collect_descriptive_evidence(
        record,
        page_fetcher=StubPageFetcher(
            '<html><head><meta property="og:description" content="Page description."></head></html>'
        ),
    )

    assert len(evidence) == 1
    assert evidence[0].evidence_type == PAGE_DESCRIPTION_EVIDENCE
    assert evidence[0].text == "Page description."
    assert evidence[0].source_url == "https://openlibrary.org/books/OL1M/Example-Title"
    assert evidence[0].quality_flags == ["trusted_source_page_description"]
