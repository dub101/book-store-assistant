from book_store_assistant.sources.national.cerlalc import CerlalcHtmlSource


class ArgentinaISBNSource(CerlalcHtmlSource):
    source_name = "argentina_isbn"
    base_url = "https://www.isbn.org.ar/web/buscar-detalle.php"
    editorial_labels = ("Editorial", "Sello", "Editor")
    url_template = "{base_url}?isbn={isbn}"
