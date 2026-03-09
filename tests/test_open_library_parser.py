from book_store_assistant.sources.open_library_parser import parse_open_library_payload


def test_parse_open_library_payload_returns_source_record() -> None:
    payload = {
        "ISBN:9780306406157": {
            "title": "Example Title",
            "subtitle": "Example Subtitle",
            "authors": [
                {"name": "Author One"},
                {"name": "Author Two"},
            ],
            "publishers": [
                {"name": "Example Editorial"},
            ],
            "cover": {
                "medium": "https://example.com/cover.jpg",
            },
        }
    }

    record = parse_open_library_payload(payload, "9780306406157")

    assert record is not None
    assert record.source_name == "open_library"
    assert record.isbn == "9780306406157"
    assert record.title == "Example Title"
    assert record.subtitle == "Example Subtitle"
    assert record.author == "Author One, Author Two"
    assert record.editorial == "Example Editorial"
    assert str(record.cover_url) == "https://example.com/cover.jpg"


def test_parse_open_library_payload_returns_none_when_isbn_is_missing() -> None:
    payload = {}

    record = parse_open_library_payload(payload, "9780306406157")

    assert record is None
