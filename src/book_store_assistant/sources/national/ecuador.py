from book_store_assistant.sources.national.cerlalc import CerlalcHtmlSource


class EcuadorISBNSource(CerlalcHtmlSource):
    source_name = "ecuador_isbn"
    base_url = "https://isbnecuador.com/catalogo.php"
