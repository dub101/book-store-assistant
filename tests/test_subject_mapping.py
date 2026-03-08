import book_store_assistant.subject_mapping as subject_mapping


def test_has_subjects_returns_false_when_catalog_is_empty() -> None:
    assert subject_mapping.has_subjects() is False
