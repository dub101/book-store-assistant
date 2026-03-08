from book_store_assistant.subject_selection import select_subject


def test_select_subject_returns_matching_allowed_subject() -> None:
    selected = select_subject("narrativa", ["Narrativa", "Historia"])

    assert selected == "Narrativa"


def test_select_subject_returns_none_when_candidate_is_not_allowed() -> None:
    selected = select_subject("Poesia", ["Narrativa", "Historia"])

    assert selected is None
