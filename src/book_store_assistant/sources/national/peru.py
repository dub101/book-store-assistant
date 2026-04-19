from book_store_assistant.sources.national.cerlalc import CerlalcHtmlSource


class PeruISBNSource(CerlalcHtmlSource):
    source_name = "peru_isbn"
    base_url = "https://isbn.bnp.gob.pe/catalogo.php"
    editorial_labels = ("Editorial", "Sello")
