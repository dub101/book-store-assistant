from book_store_assistant.sources.search_backend import (
    FallbackSearchBackend,
    _decode_search_result_link,
    _extract_bing_result_links,
    _extract_brave_result_links,
    _extract_yahoo_result_links,
    build_default_search_backend,
)


def test_decode_search_result_link_unwraps_protocol_relative_duckduckgo_redirect() -> None:
    link = (
        "//duckduckgo.com/l/?uddg="
        "https%3A%2F%2Fwww.planetadelibros.com%2Flibro%2Fejemplo%2F123"
    )

    assert _decode_search_result_link(link) == (
        "https://www.planetadelibros.com/libro/ejemplo/123"
    )


def test_decode_search_result_link_unwraps_duckduckgo_ad_target() -> None:
    link = (
        "https://duckduckgo.com/y.js?u3="
        "https%3A%2F%2Fwww.casadellibro.com%2Flibro%2Fejemplo%2F123"
    )

    assert _decode_search_result_link(link) == (
        "https://www.casadellibro.com/libro/ejemplo/123"
    )


def test_decode_search_result_link_unwraps_yahoo_redirect() -> None:
    link = (
        "https://r.search.yahoo.com/_ylt=abc/RV=2/RE=123/RO=10/"
        "RU=https%3a%2f%2fwww.penguinlibros.com%2fes%2flibro%2fejemplo%2f123/"
        "RK=2/RS=xyz-"
    )

    assert _decode_search_result_link(link) == (
        "https://www.penguinlibros.com/es/libro/ejemplo/123"
    )


def test_extract_bing_result_links_returns_direct_allowed_results() -> None:
    html = """
    <html>
      <body>
        <li class="b_algo">
          <h2><a href="https://www.planetadelibros.com/libro/ejemplo/123">Ejemplo</a></h2>
        </li>
        <li class="b_algo">
          <h2><a href="https://www.amazon.com/otro">Otro</a></h2>
        </li>
      </body>
    </html>
    """

    assert _extract_bing_result_links(
        html,
        allowed_domains=("planetadelibros.com",),
        limit=10,
    ) == ["https://www.planetadelibros.com/libro/ejemplo/123"]


def test_extract_brave_result_links_skips_search_engine_links() -> None:
    html = """
    <html>
      <body>
        <a href="https://search.brave.com/search?q=isbn">Buscar</a>
        <a href="https://account.brave.com/">Cuenta</a>
        <a href="https://www.penguinlibros.com/es/literatura/339875-libro-cien-anos-9788466373531">
          Libro
        </a>
      </body>
    </html>
    """

    assert _extract_brave_result_links(
        html,
        allowed_domains=("penguinlibros.com",),
        limit=10,
    ) == [
        "https://www.penguinlibros.com/es/literatura/339875-libro-cien-anos-9788466373531"
    ]


def test_extract_yahoo_result_links_returns_decoded_allowed_results() -> None:
    html = """
    <html>
      <body>
        <a href="https://r.search.yahoo.com/_ylt=abc/RV=2/RE=123/RO=10/RU=https%3a%2f%2fwww.yahoo.com%2f/RK=2/RS=xyz-">Yahoo</a>
        <a href="https://r.search.yahoo.com/_ylt=abc/RV=2/RE=123/RO=10/RU=https%3a%2f%2fwww.planetadelibros.com%2flibro%2fejemplo%2f123/RK=2/RS=xyz-">Libro</a>
      </body>
    </html>
    """

    assert _extract_yahoo_result_links(
        html,
        allowed_domains=("planetadelibros.com",),
        limit=10,
    ) == ["https://www.planetadelibros.com/libro/ejemplo/123"]


def test_build_default_search_backend_uses_yahoo_then_duckduckgo_then_bing() -> None:
    backend = build_default_search_backend(timeout_seconds=5)

    assert isinstance(backend, FallbackSearchBackend)
    assert [type(searcher).__name__ for searcher in backend.backends] == [
        "YahooHtmlSearcher",
        "DuckDuckGoHtmlSearcher",
        "BingHtmlSearcher",
    ]
