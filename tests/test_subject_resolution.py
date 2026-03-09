from book_store_assistant.resolution.subject_resolution import resolve_subject


def test_resolve_subject_returns_first_allowed_match() -> None:
    subject = resolve_subject(
        ["Unknown", "Narrativa", "Historia"],
        ["Narrativa", "Historia"],
    )

    assert subject == "Narrativa"


def test_resolve_subject_extracts_match_from_compound_category() -> None:
    subject = resolve_subject(
        ["Fiction / Narrativa", "Historia, Ensayo"],
        ["Narrativa", "Historia"],
    )

    assert subject == "Narrativa"


def test_resolve_subject_extracts_match_from_hierarchical_category() -> None:
    subject = resolve_subject(
        ["Literatura > Narrativa", "Biografia; Historia"],
        ["Narrativa", "Historia"],
    )

    assert subject == "Narrativa"


def test_resolve_subject_returns_none_when_no_candidate_matches() -> None:
    subject = resolve_subject(
        ["Poetry", "Drama"],
        ["Narrativa", "Historia"],
    )

    assert subject is None
