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
                    "language": "es",
                    "imageLinks": {
                        "thumbnail": "https://example.com/cover.jpg",
                    },
                }
            }
        ]
    }

    record = parse_google_books_payload(payload, "9780306406157")

    assert record is not None
    assert record.source_name == "google_books"
    assert record.isbn == "9780306406157"
    assert record.author == "Author One, Author Two"
    assert str(record.cover_url) == "https://example.com/cover.jpg"
