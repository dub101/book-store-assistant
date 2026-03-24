from book_store_assistant.sources.page_descriptions import (
    extract_description_candidates_from_html,
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


def test_extract_description_candidates_from_html_reads_backcover_style_sections() -> None:
    html = """
    <html>
      <body>
        <h2>Contracubierta</h2>
        <div>
          Esta contracubierta desarrolla con suficiente detalle el conflicto, el tono y el
          contexto narrativo de la obra para servir como evidencia confiable.
        </div>
      </body>
    </html>
    """

    assert extract_description_candidates_from_html(html) == [
        (
            "body_description",
            "Esta contracubierta desarrolla con suficiente detalle el conflicto, el tono y el "
            "contexto narrativo de la obra para servir como evidencia confiable.",
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
