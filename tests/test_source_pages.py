from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult
from book_store_assistant.sources.source_pages import augment_fetch_results_with_source_pages


class StubPageFetcher:
    def __init__(self, html_by_url: dict[str, str | None]) -> None:
        self.html_by_url = html_by_url

    def fetch_text(self, url: str) -> str | None:
        return self.html_by_url.get(url)


def test_source_page_enrichment_uses_google_books_source_url_to_fill_editorial() -> None:
    source_url = (
        "https://books.google.com.co/books?id=70PV0AEACAAJ"
        "&dq=isbn:9788401027970&hl=es&source=gbs_api"
    )
    fetch_results = [
        FetchResult(
            isbn="9788401027970",
            record=SourceBookRecord(
                source_name="bne + google_books",
                isbn="9788401027970",
                source_url=source_url,
                title="El niño que perdió la cordura",
                author="Julia Navarro Coll",
                editorial=None,
            ),
            errors=[],
            issue_codes=[],
        )
    ]
    html = """
    <html>
      <head>
        <title>El niño que perdió la guerra - Julia Navarro - Google Libros</title>
      </head>
      <body>
        <div class="bookinfo_sectionwrap">
          <div><a href="#">Julia Navarro</a></div>
          <div>
            <span dir="ltr">Plaza &amp; Janés</span>,
            2024 -
            <span dir="ltr">637 páginas</span>
          </div>
        </div>
      </body>
    </html>
    """

    augmented = augment_fetch_results_with_source_pages(
        fetch_results,
        timeout_seconds=5.0,
        page_fetcher=StubPageFetcher({source_url: html}),
    )

    assert augmented[0].record is not None
    assert augmented[0].record.title == "El niño que perdió la guerra"
    assert augmented[0].record.author == "Julia Navarro Coll"
    assert augmented[0].record.editorial == "Plaza & Janés"
    assert augmented[0].diagnostics[0]["stage"] == "source_pages"
    assert augmented[0].diagnostics[0]["changed_fields"] == ["title", "editorial"]
