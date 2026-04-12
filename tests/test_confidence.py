"""Tests for the source_confidence function covering all branches."""


from book_store_assistant.sources.confidence import source_confidence


class TestSourceConfidence:
    def test_bne(self) -> None:
        assert source_confidence("bne") == 1.0

    def test_bne_case_insensitive(self) -> None:
        assert source_confidence("BNE") == 1.0
        assert source_confidence(" Bne ") == 1.0

    def test_isbndb(self) -> None:
        assert source_confidence("isbndb") == 0.9

    def test_publisher_page(self) -> None:
        assert source_confidence("publisher_page_planeta") == 1.0

    def test_publisher_page_generic(self) -> None:
        assert source_confidence("publisher_page") == 1.0

    def test_web_search_official(self) -> None:
        assert source_confidence("web_search_official_site") == 0.98

    def test_web_search_official_bare(self) -> None:
        assert source_confidence("web_search_official") == 0.98

    def test_web_search(self) -> None:
        assert source_confidence("web_search_generic") == 0.85

    def test_web_search_bare(self) -> None:
        assert source_confidence("web_search") == 0.85

    def test_google_books(self) -> None:
        assert source_confidence("google_books") == 0.75

    def test_open_library(self) -> None:
        assert source_confidence("open_library") == 0.6

    def test_retailer_page(self) -> None:
        assert source_confidence("retailer_page_amazon") == 0.55

    def test_retailer_page_bare(self) -> None:
        assert source_confidence("retailer_page") == 0.55

    def test_ai_enriched(self) -> None:
        assert source_confidence("ai_enriched") == 0.3

    def test_fetch_error(self) -> None:
        assert source_confidence("fetch_error") == 0.0

    def test_unknown_source_returns_default(self) -> None:
        assert source_confidence("unknown_source") == 0.5

    def test_completely_novel_source(self) -> None:
        assert source_confidence("some_new_provider") == 0.5

    def test_composite_bne_plus_google_books(self) -> None:
        result = source_confidence("bne + google_books")
        assert result == 1.0  # max(1.0, 0.75)

    def test_composite_google_books_plus_open_library(self) -> None:
        result = source_confidence("google_books + open_library")
        assert result == 0.75  # max(0.75, 0.6)

    def test_composite_three_sources(self) -> None:
        result = source_confidence("open_library + ai_enriched + isbndb")
        assert result == 0.9  # max(0.6, 0.3, 0.9)

    def test_composite_with_unknown(self) -> None:
        result = source_confidence("unknown + fetch_error")
        assert result == 0.5  # max(0.5, 0.0)

    def test_web_search_official_has_priority_over_web_search(self) -> None:
        """web_search_official should match before plain web_search."""
        assert source_confidence("web_search_official_foo") == 0.98
        assert source_confidence("web_search_foo") == 0.85

    def test_publisher_page_has_priority_over_retailer_page(self) -> None:
        assert source_confidence("publisher_page_example") == 1.0
        assert source_confidence("retailer_page_example") == 0.55
