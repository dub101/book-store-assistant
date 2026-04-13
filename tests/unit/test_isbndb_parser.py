from book_store_assistant.sources.isbndb_parser import parse_isbndb_payload


def test_parse_valid_complete_payload() -> None:
    payload = {
        "book": {
            "title": "Cien anos de soledad",
            "title_long": "Cien anos de soledad: Edicion conmemorativa",
            "authors": ["Gabriel Garcia Marquez"],
            "publisher": "Editorial Sudamericana",
            "synopsis": "A masterpiece of magical realism.",
            "subjects": ["Fiction", "Latin American Literature"],
            "image": "https://covers.example.com/cover.jpg",
            "language": "spa",
        }
    }

    record = parse_isbndb_payload(payload, "9789500286442")

    assert record is not None
    assert record.source_name == "isbndb"
    assert record.isbn == "9789500286442"
    assert record.title == "Cien anos de soledad: Edicion conmemorativa"
    assert record.subtitle == "Edicion conmemorativa"
    assert record.author == "Gabriel Garcia Marquez"
    assert record.editorial == "Editorial Sudamericana"
    assert record.synopsis == "A masterpiece of magical realism."
    assert record.categories == ["Fiction", "Latin American Literature"]
    assert str(record.cover_url) == "https://covers.example.com/cover.jpg"
    assert record.language == "es"
    assert record.source_url is None
    assert record.raw_source_payload is None


def test_parse_payload_with_missing_fields() -> None:
    payload = {
        "book": {
            "title": "Minimal Book",
        }
    }

    record = parse_isbndb_payload(payload, "9780306406157")

    assert record is not None
    assert record.title == "Minimal Book"
    assert record.subtitle is None
    assert record.author is None
    assert record.editorial is None
    assert record.synopsis is None
    assert record.categories == []
    assert record.cover_url is None
    assert record.language is None


def test_parse_payload_no_book_key_returns_none() -> None:
    payload = {"error": "not found"}

    result = parse_isbndb_payload(payload, "9780306406157")

    assert result is None


def test_parse_payload_empty_book_object_returns_none() -> None:
    """An empty dict is falsy in Python, so parse_isbndb_payload returns None."""
    payload = {"book": {}}

    record = parse_isbndb_payload(payload, "9780306406157")

    assert record is None


def test_parse_payload_book_not_dict_returns_none() -> None:
    payload = {"book": "not a dict"}

    result = parse_isbndb_payload(payload, "9780306406157")

    assert result is None


def test_parse_payload_book_is_none_returns_none() -> None:
    payload = {"book": None}

    result = parse_isbndb_payload(payload, "9780306406157")

    assert result is None


def test_subtitle_extraction_from_title_long() -> None:
    payload = {
        "book": {
            "title": "Don Quijote",
            "title_long": "Don Quijote: Segunda Parte",
        }
    }

    record = parse_isbndb_payload(payload, "9780306406157")

    assert record is not None
    assert record.subtitle == "Segunda Parte"
    assert record.title == "Don Quijote: Segunda Parte"


def test_subtitle_not_extracted_when_no_colon_separator() -> None:
    payload = {
        "book": {
            "title": "Short",
            "title_long": "Short but longer without colon",
        }
    }

    record = parse_isbndb_payload(payload, "9780306406157")

    assert record is not None
    assert record.subtitle is None


def test_subtitle_not_extracted_when_title_long_equals_title() -> None:
    payload = {
        "book": {
            "title": "Same Title",
            "title_long": "Same Title",
        }
    }

    record = parse_isbndb_payload(payload, "9780306406157")

    assert record is not None
    assert record.subtitle is None


def test_subtitle_not_extracted_when_title_long_is_none() -> None:
    payload = {
        "book": {
            "title": "Only Title",
            "title_long": None,
        }
    }

    record = parse_isbndb_payload(payload, "9780306406157")

    assert record is not None
    assert record.subtitle is None


def test_authors_list_joined_with_comma() -> None:
    payload = {
        "book": {
            "title": "Collaborative Work",
            "authors": ["Author One", "Author Two", "Author Three"],
        }
    }

    record = parse_isbndb_payload(payload, "9780306406157")

    assert record is not None
    assert record.author == "Author One, Author Two, Author Three"


def test_authors_empty_list_gives_none() -> None:
    payload = {
        "book": {
            "title": "Anonymous",
            "authors": [],
        }
    }

    record = parse_isbndb_payload(payload, "9780306406157")

    assert record is not None
    assert record.author is None


def test_authors_none_gives_none() -> None:
    payload = {
        "book": {
            "title": "No Authors Field",
            "authors": None,
        }
    }

    record = parse_isbndb_payload(payload, "9780306406157")

    assert record is not None
    assert record.author is None


def test_title_long_preferred_over_title() -> None:
    payload = {
        "book": {
            "title": "Short",
            "title_long": "Short: Extended Edition",
        }
    }

    record = parse_isbndb_payload(payload, "9780306406157")

    assert record is not None
    assert record.title == "Short: Extended Edition"


def test_title_used_when_title_long_missing() -> None:
    payload = {
        "book": {
            "title": "Only Short Title",
        }
    }

    record = parse_isbndb_payload(payload, "9780306406157")

    assert record is not None
    assert record.title == "Only Short Title"


def test_language_normalized() -> None:
    payload = {
        "book": {
            "title": "English Book",
            "language": "eng",
        }
    }

    record = parse_isbndb_payload(payload, "9780306406157")

    assert record is not None
    assert record.language == "en"


def test_unknown_language_passed_through() -> None:
    payload = {
        "book": {
            "title": "French Book",
            "language": "fre",
        }
    }

    record = parse_isbndb_payload(payload, "9780306406157")

    assert record is not None
    assert record.language == "fre"
