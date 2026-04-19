from book_store_assistant.sources.national.cerlalc import CerlalcHtmlSource


class ColombiaISBNSource(CerlalcHtmlSource):
    source_name = "colombia_isbn"
    base_url = "https://isbn.camlibro.com.co/catalogo.php"
    editorial_labels = ("Editorial", "Sello", "Editor")
