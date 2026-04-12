from book_store_assistant.bibliographic.resolution import (
    _clean_author,
    _clean_editorial,
    _clean_title,
)

# -- _clean_editorial --


def test_clean_editorial_strips_bracketed_city_prefix() -> None:
    assert _clean_editorial("[Barcelona], Debolsillo") == "Debolsillo"


def test_clean_editorial_strips_named_city() -> None:
    assert _clean_editorial("Madrid, Catedra") == "Catedra"


def test_clean_editorial_picks_last_segment_after_semicolons() -> None:
    result = _clean_editorial("Espasa Calpe ;, Barcelona, Planeta")
    assert result == "Planeta"


def test_clean_editorial_strips_parenthetical_city() -> None:
    result = _clean_editorial("Boadilla del Monte (Madrid), SM")
    assert result == "SM"


def test_clean_editorial_strips_editorial_prefix() -> None:
    assert _clean_editorial("Editorial Planeta") == "Planeta"


def test_clean_editorial_preserves_short_names() -> None:
    # "B" is only 1 char, so _normalize_editorial_name keeps the original
    assert _clean_editorial("Ediciones B") == "Ediciones B"


def test_clean_editorial_strips_ediciones_prefix() -> None:
    result = _clean_editorial("Ediciones Destino")
    assert result == "Destino"


def test_clean_editorial_none_returns_none() -> None:
    assert _clean_editorial(None) is None


def test_clean_editorial_empty_string_returns_none() -> None:
    assert _clean_editorial("   ") is None


# -- _clean_title --


def test_clean_title_strips_collection_annotations() -> None:
    result = _clean_title("La casa verde (Coleccion Austral)")
    assert result == "La casa verde"


def test_clean_title_strips_texto_impreso_artifact() -> None:
    result = _clean_title("El amor en los tiempos del colera [Texto impreso]")
    assert result == "El amor en los tiempos del colera"


def test_clean_title_strips_alt_language_suffix() -> None:
    result = _clean_title("Cien anos de soledad = One Hundred Years of Solitude")
    assert result == "Cien anos de soledad"


def test_clean_title_strips_alt_language_with_slash() -> None:
    result = _clean_title("Don Quijote / Don Quixote")
    assert result == "Don Quijote"


def test_clean_title_strips_series_prefix() -> None:
    result = _clean_title("3. El prisionero de Azkaban")
    assert result == "El prisionero de Azkaban"


def test_clean_title_none_returns_none() -> None:
    assert _clean_title(None) is None


def test_clean_title_strips_subtitle_from_end() -> None:
    result = _clean_title("Main Title : The Subtitle", subtitle="The Subtitle")
    assert result == "Main Title"


def test_clean_title_strips_recurso_electronico() -> None:
    result = _clean_title("Historia de Espana [recurso electronico]")
    assert result == "Historia de Espana"


# -- _clean_author --


def test_clean_author_normalizes_initials() -> None:
    result = _clean_author("J. R. R. Tolkien")
    assert result == "J.R.R. Tolkien"


def test_clean_author_preserves_single_initial() -> None:
    result = _clean_author("J. Tolkien")
    assert result == "J. Tolkien"


def test_clean_author_none_returns_none() -> None:
    assert _clean_author(None) is None


def test_clean_author_strips_extra_whitespace() -> None:
    result = _clean_author("  Gabriel   Garcia   Marquez  ")
    assert result == "Gabriel Garcia Marquez"
