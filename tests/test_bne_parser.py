from book_store_assistant.sources.bne_parser import parse_bne_sru_payload


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
          <description>Una novela ambientada en la Barcelona de posguerra.</description>
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
    assert record.synopsis == "Una novela ambientada en la Barcelona de posguerra."
    assert record.categories == ["Novela espanola"]
    assert record.language == "es"


def test_parse_bne_sru_payload_returns_none_when_no_records_exist() -> None:
    payload = (
        '<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">'
        "<records />"
        "</searchRetrieveResponse>"
    )

    assert parse_bne_sru_payload(payload, "9780306406157") is None
