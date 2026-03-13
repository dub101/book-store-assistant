from book_store_assistant.resolution.subject_resolution import resolve_subject


def test_resolve_subject_returns_first_allowed_match() -> None:
    subject = resolve_subject(
        ["Unknown", "Narrativa", "Historia"],
        [["Narrativa"], ["Historia"]],
    )

    assert subject == "Narrativa"


def test_resolve_subject_extracts_match_from_compound_category() -> None:
    subject = resolve_subject(
        ["Fiction / Narrativa", "Historia, Ensayo"],
        [["Narrativa"], ["Historia"]],
    )

    assert subject == "Narrativa"


def test_resolve_subject_extracts_match_from_hierarchical_category() -> None:
    subject = resolve_subject(
        ["Literatura > Narrativa", "Biografia; Historia"],
        [["Narrativa"], ["Historia"]],
    )

    assert subject == "Narrativa"


def test_resolve_subject_matches_alias_to_canonical_subject() -> None:
    subject = resolve_subject(
        ["Fiction", "Historical"],
        [["Narrativa", "Fiction", "Novel"], ["Historia", "Historical"]],
    )

    assert subject == "Narrativa"


def test_resolve_subject_splits_ampersand_categories() -> None:
    subject = resolve_subject(
        ["Fiction & Literature"],
        [["Narrativa", "Fiction"], ["Literatura", "Literature"]],
    )

    assert subject == "Narrativa"


def test_resolve_subject_matches_embedded_alias_in_larger_phrase() -> None:
    subject = resolve_subject(
        ["Historia argentina"],
        [["Narrativa", "Fiction"], ["Historia", "Historical"]],
    )

    assert subject == "Historia"


def test_resolve_subject_returns_none_when_no_candidate_matches() -> None:
    subject = resolve_subject(
        ["Poetry", "Drama"],
        [["Narrativa"], ["Historia"]],
    )

    assert subject is None


def test_resolve_subject_prefers_the_most_supported_controlled_match() -> None:
    subject = resolve_subject(
        ["Historical", "Fiction", "Novel"],
        [["Narrativa", "Fiction", "Novel"], ["Historia", "Historical"]],
    )

    assert subject == "Narrativa"


def test_resolve_subject_maps_bne_fiction_category_to_catalog_fiction() -> None:
    subject = resolve_subject(
        ['821.134.2-31"19"'],
        [["FICCION", "Fiction", "Novel"], ["Historia", "Historical"]],
    )

    assert subject == "FICCION"
