from book_store_assistant.sources.national.cerlalc import CerlalcHtmlSource


class ChileISBNSource(CerlalcHtmlSource):
    source_name = "chile_isbn"
    base_url = "https://isbnchile.cl/catalogo.php"
    editorial_labels = ("Editorial", "Sello", "Editor")
