from book_store_assistant.subject_selection import select_subject


def test_select_subject_returns_matching_allowed_subject() -> None:
    selected = select_subject("narrativa", ["Narrativa", "Historia"])

    assert selected == "Narrativa"


def test_select_subject_ignores_extra_whitespace_and_hyphens() -> None:
    selected = select_subject("ciencia-ficcion", ["Ciencia ficcion", "Historia"])

    assert selected == "Ciencia ficcion"


def test_select_subject_ignores_accents() -> None:
    selected = select_subject("Poesía", ["Poesia", "Historia"])

    assert selected == "Poesia"


def test_select_subject_matches_embedded_alias_with_word_boundaries() -> None:
    selected = select_subject(
        "Juvenile Fiction",
        [["Narrativa", "Fiction"], ["Historia", "Historical"]],
    )

    assert selected == "Narrativa"


def test_select_subject_does_not_match_partial_words() -> None:
    selected = select_subject(
        "Historias breves",
        [["Historia"], ["Narrativa"]],
    )

    assert selected is None


def test_select_subject_returns_none_when_candidate_is_not_allowed() -> None:
    selected = select_subject("Ensayo", ["Narrativa", "Historia"])

    assert selected is None
