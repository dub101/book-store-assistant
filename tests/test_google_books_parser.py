from book_store_assistant.sources.google_books_parser import parse_google_books_payload


def test_parse_google_books_payload_returns_source_record() -> None:
    payload = {
        "items": [
            {
                "volumeInfo": {
                    "title": "Example Title",
                    "subtitle": "Example Subtitle",
                    "authors": ["Author One", "Author Two"],
                    "publisher": "Example Editorial",
                    "description": "Resumen del libro.",
                    "language": "spa",
                    "categories": ["Fiction", "Literary Collections"],
                    "imageLinks": {
                        "thumbnail": "https://example.com/cover.jpg",
                    },
                    "infoLink": "https://example.com/book",
                }
            }
        ]
    }

    record = parse_google_books_payload(payload, "9780306406157")

    assert record is not None
    assert record.source_name == "google_books"
    assert record.isbn == "9780306406157"
    assert str(record.source_url) == "https://example.com/book"
    assert record.author == "Author One, Author Two"
    assert record.language == "es"
    assert record.categories == ["Fiction", "Literary Collections"]
    assert str(record.cover_url) == "https://example.com/cover.jpg"


def test_parse_google_books_payload_keeps_unknown_language_codes() -> None:
    payload = {
        "items": [
            {
                "volumeInfo": {
                    "title": "Example Title",
                    "language": "fre",
                }
            }
        ]
    }

    record = parse_google_books_payload(payload, "9780306406157")

    assert record is not None
    assert record.language == "fre"


def test_parse_google_books_payload_falls_back_to_search_info_snippet() -> None:
    payload = {
        "items": [
            {
                "volumeInfo": {
                    "title": "Example Title",
                    "language": "es",
                },
                "searchInfo": {
                    "textSnippet": (
                        "Primera novela &lt;b&gt;inolvidable&lt;/b&gt; del autor."
                    )
                },
            }
        ]
    }

    record = parse_google_books_payload(payload, "9780306406157")

    assert record is not None
    assert record.synopsis == "Primera novela inolvidable del autor."
