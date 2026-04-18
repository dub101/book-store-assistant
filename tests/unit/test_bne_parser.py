import pytest
from defusedxml.common import EntitiesForbidden

from book_store_assistant.sources.bne_parser import _is_bne_catalog_note, parse_bne_sru_payload


def test_parse_bne_sru_payload_extracts_book_metadata() -> None:
    payload = """\
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <records>
    <record>
      <recordData>
        <dc xmlns="http://purl.org/dc/elements/1.1/">
          <title>La sombra del viento</title>
          <creator>Carlos Ruiz Zafon</creator>
          <publisher>Planeta</publisher>
          <description>Una novela ambientada en la Barcelona de posguerra, llena de misterio, intriga y aventuras literarias.</description>
          <subject>Novela espanola</subject>
          <language>spa</language>
          <identifier>https://catalogo.bne.es/discovery/fulldisplay?docid=alma99123</identifier>
        </dc>
      </recordData>
    </record>
  </records>
</searchRetrieveResponse>
"""

    record = parse_bne_sru_payload(payload, "9780306406157")

    assert record is not None
    assert record.source_name == "bne"
    assert record.title == "La sombra del viento"
    assert record.author == "Carlos Ruiz Zafon"
    assert record.editorial == "Planeta"
    assert record.synopsis == (
        "Una novela ambientada en la Barcelona de posguerra,"
        " llena de misterio, intriga y aventuras literarias."
    )
    assert record.categories == ["Novela espanola"]
    assert record.language == "es"


def test_parse_bne_sru_payload_returns_none_when_no_records_exist() -> None:
    payload = (
        '<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">'
        "<records />"
        "</searchRetrieveResponse>"
    )

    assert parse_bne_sru_payload(payload, "9780306406157") is None


# -- _is_bne_catalog_note --


def test_is_bne_catalog_note_returns_true_for_short_text() -> None:
    assert _is_bne_catalog_note("Novela") is True
    assert _is_bne_catalog_note("p. 120-135") is True
    assert _is_bne_catalog_note("x" * 79) is True


def test_is_bne_catalog_note_returns_true_for_titulo_original() -> None:
    assert _is_bne_catalog_note("Título original: The Shadow of the Wind") is True


def test_is_bne_catalog_note_returns_true_for_penguin_random_house() -> None:
    text = (
        "Penguin Random House Grupo Editorial publica esta obra "
        "con la garantia de calidad que nos caracteriza desde hace muchos anos."
    )
    assert _is_bne_catalog_note(text) is True


def test_is_bne_catalog_note_returns_false_for_long_genuine_synopsis() -> None:
    text = (
        "En la Barcelona de 1945, un muchacho es conducido por su padre a un "
        "misterioso lugar oculto en el corazon de la ciudad vieja donde descubre "
        "un libro maldito que cambiara el rumbo de su vida."
    )
    assert len(text) > 100
    assert _is_bne_catalog_note(text) is False


def test_parse_bne_sru_payload_filters_out_catalog_notes_from_synopsis() -> None:
    payload = """\
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <records>
    <record>
      <recordData>
        <dc xmlns="http://purl.org/dc/elements/1.1/">
          <title>El Quijote</title>
          <creator>Cervantes</creator>
          <publisher>Planeta</publisher>
          <description>Traduccion de M. Smith</description>
          <subject>Novela</subject>
          <language>spa</language>
        </dc>
      </recordData>
    </record>
  </records>
</searchRetrieveResponse>
"""

    record = parse_bne_sru_payload(payload, "9780000000001")

    assert record is not None
    assert record.synopsis is None


def test_parse_bne_sru_payload_keeps_genuine_synopsis() -> None:
    genuine_synopsis = (
        "En la Barcelona de 1945, un muchacho es conducido por su padre a un "
        "misterioso lugar oculto en el corazon de la ciudad vieja donde descubre "
        "un libro maldito que cambiara el rumbo de su vida para siempre."
    )
    payload = f"""\
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <records>
    <record>
      <recordData>
        <dc xmlns="http://purl.org/dc/elements/1.1/">
          <title>La sombra del viento</title>
          <creator>Carlos Ruiz Zafon</creator>
          <publisher>Planeta</publisher>
          <description>{genuine_synopsis}</description>
          <subject>Novela</subject>
          <language>spa</language>
        </dc>
      </recordData>
    </record>
  </records>
</searchRetrieveResponse>
"""

    record = parse_bne_sru_payload(payload, "9780000000002")

    assert record is not None
    assert record.synopsis == genuine_synopsis


def test_parse_bne_sru_payload_rejects_entity_expansion_attack() -> None:
    """A hostile or MITM'd BNE response cannot trigger a billion-laughs DoS."""
    payload = """\
<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <records><record><recordData><dc><title>&lol3;</title></dc></recordData></record></records>
</searchRetrieveResponse>
"""

    with pytest.raises(EntitiesForbidden):
        parse_bne_sru_payload(payload, "9780000000002")
