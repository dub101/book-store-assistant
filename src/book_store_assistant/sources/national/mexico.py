from book_store_assistant.sources.national.cerlalc import CerlalcHtmlSource


class MexicoISBNSource(CerlalcHtmlSource):
    source_name = "mexico_isbn"
    base_url = "https://isbnmexico.indautor.cerlalc.org/catalogo.php"
    editorial_labels = ("Editorial", "Sello editorial", "Sello")
