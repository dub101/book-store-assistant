from book_store_assistant.enrichment.evidence import (
    DIRECT_SOURCE_RECORD_EVIDENCE,
    SOURCE_AUTHOR_EVIDENCE,
    SOURCE_EDITORIAL_EVIDENCE,
    SOURCE_PAGE_BODY_DESCRIPTION_EVIDENCE,
    SOURCE_PAGE_META_DESCRIPTION_EVIDENCE,
    SOURCE_PAGE_SCRAPED_EVIDENCE,
    SOURCE_PAGE_STRUCTURED_DATA_EVIDENCE,
    SOURCE_PAGE_STRUCTURED_EVIDENCE,
    SOURCE_SUBTITLE_EVIDENCE,
    SOURCE_SYNOPSIS_EVIDENCE,
    SOURCE_TITLE_EVIDENCE,
    collect_descriptive_evidence,
)
from book_store_assistant.enrichment.page_fetch import (
    extract_description_candidates_from_html,
    extract_description_from_html,
)
from book_store_assistant.sources.models import SourceBookRecord


class StubPageFetcher:
    def __init__(self, html: str | None) -> None:
        self.html = html

    def fetch_text(self, url: str) -> str | None:
        return self.html


def test_extract_description_from_html_reads_meta_description() -> None:
    html = (
        "<html><head><meta name=\"description\" "
        "content=\"Example description with enough detail for evidence extraction.\"></head></html>"
    )

    assert extract_description_from_html(html) == (
        "Example description with enough detail for evidence extraction."
    )


def test_extract_description_candidates_from_html_reads_meta_description() -> None:
    html = (
        "<html><head><meta name=\"description\" "
        "content=\"Example description with enough detail for evidence extraction.\"></head></html>"
    )

    assert extract_description_candidates_from_html(html) == [
        (
            "meta_description",
            "Example description with enough detail for evidence extraction.",
        )
    ]


def test_extract_description_candidates_from_html_reads_book_json_ld_description() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Book",
            "name": "Example Title",
            "description": "A detailed structured description from the trusted source page."
          }
        </script>
      </head>
    </html>
    """

    assert extract_description_candidates_from_html(html) == [
        (
            "structured_data",
            "A detailed structured description from the trusted source page.",
        )
    ]


def test_extract_description_candidates_from_html_reads_body_description() -> None:
    html = """
    <html>
      <body>
        <div class="book-description">
          <p>This body description contains enough grounded detail to be kept as evidence.</p>
        </div>
      </body>
    </html>
    """

    assert extract_description_candidates_from_html(html) == [
        (
            "body_description",
            "This body description contains enough grounded detail to be kept as evidence.",
        )
    ]


def test_extract_description_candidates_from_html_reads_google_books_embedded_data() -> None:
    html = r"""
    <html>
      <body>
        <script>
          window.__GBS_DATA__ = {
            "volume": {
              "description": "Google Books embedded description for trusted evidence."
            }
          };
        </script>
      </body>
    </html>
    """

    assert extract_description_candidates_from_html(
        html,
        source_url="https://books.google.com/books?id=abc123",
    ) == [
        (
            "google_books_embedded_data",
            "Google Books embedded description for trusted evidence.",
        )
    ]


def test_extract_description_candidates_from_html_reads_open_library_embedded_data() -> None:
    html = r"""
    <html>
      <body>
        <script>
          window.__OL_DATA__ = {
            "book": {
              "description": {
                "value": "Detailed Open Library embedded description with enough grounded detail."
              }
            }
          };
        </script>
      </body>
    </html>
    """

    assert extract_description_candidates_from_html(
        html,
        source_url="https://openlibrary.org/books/OL1M/Example-Title",
    ) == [
        (
            "open_library_embedded_data",
            "Detailed Open Library embedded description with enough grounded detail.",
        )
    ]


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
    assert evidence[0].evidence_origin == DIRECT_SOURCE_RECORD_EVIDENCE
    assert evidence[0].extraction_method == "source_synopsis_field"


def test_collect_descriptive_evidence_includes_direct_bibliographic_fields() -> None:
    record = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        title="Example Title",
        subtitle="Example Subtitle",
        author="Example Author",
        editorial="Example Editorial",
        field_sources={
            "title": "google_books",
            "subtitle": "open_library",
            "author": "google_books",
            "editorial": "open_library",
        },
    )

    evidence = collect_descriptive_evidence(record)

    assert [item.evidence_type for item in evidence] == [
        SOURCE_TITLE_EVIDENCE,
        SOURCE_SUBTITLE_EVIDENCE,
        SOURCE_AUTHOR_EVIDENCE,
        SOURCE_EDITORIAL_EVIDENCE,
    ]
    assert all(item.evidence_origin == DIRECT_SOURCE_RECORD_EVIDENCE for item in evidence)


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
            """
            <html>
              <head>
                <meta property="og:description"
                  content="Page description with enough detail to be retained as evidence.">
                <script type="application/ld+json">
                  {
                    "@context": "https://schema.org",
                    "@type": "Book",
                    "description": "Structured page description with additional grounded detail."
                  }
                </script>
              </head>
              <body>
                <section id="description">
                  Body page description with enough grounded detail to support generation.
                </section>
              </body>
            </html>
            """
        ),
    )

    assert len(evidence) == 3
    assert evidence[0].evidence_type == SOURCE_PAGE_META_DESCRIPTION_EVIDENCE
    assert evidence[0].evidence_origin == SOURCE_PAGE_SCRAPED_EVIDENCE
    assert evidence[0].text == "Page description with enough detail to be retained as evidence."
    assert evidence[0].source_url == "https://openlibrary.org/books/OL1M/Example-Title"
    assert evidence[0].extraction_method == "meta_description"
    assert evidence[0].quality_flags == ["trusted_source_page_description", "meta_description"]
    assert evidence[1].evidence_type == SOURCE_PAGE_STRUCTURED_DATA_EVIDENCE
    assert evidence[1].evidence_origin == SOURCE_PAGE_STRUCTURED_EVIDENCE
    assert evidence[1].extraction_method == "structured_data"
    assert evidence[1].quality_flags == ["trusted_source_page_description", "structured_data"]
    assert evidence[2].evidence_type == SOURCE_PAGE_BODY_DESCRIPTION_EVIDENCE
    assert evidence[2].evidence_origin == SOURCE_PAGE_SCRAPED_EVIDENCE
    assert evidence[2].extraction_method == "body_description"
    assert evidence[2].quality_flags == ["trusted_source_page_description", "body_description"]


def test_collect_descriptive_evidence_uses_source_specific_embedded_page_data() -> None:
    record = SourceBookRecord(
        source_name="google_books",
        isbn="9780306406157",
        source_url="https://books.google.com/books?id=abc123",
        language="en",
        field_sources={"source_url": "google_books"},
    )

    evidence = collect_descriptive_evidence(
        record,
        page_fetcher=StubPageFetcher(
            r"""
            <html>
              <body>
                <script>
                  window.__GBS_DATA__ = {
                    "volume": {
                      "description": "Google Books embedded description for trusted evidence."
                    }
                  };
                </script>
              </body>
            </html>
            """
        ),
    )

    assert len(evidence) == 1
    assert evidence[0].evidence_type == SOURCE_PAGE_STRUCTURED_DATA_EVIDENCE
    assert evidence[0].evidence_origin == SOURCE_PAGE_STRUCTURED_EVIDENCE
    assert evidence[0].extraction_method == "google_books_embedded_data"
    assert evidence[0].quality_flags == [
        "trusted_source_page_description",
        "google_books_embedded_data",
    ]
