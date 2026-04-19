from book_store_assistant.sources.national.cerlalc import CerlalcHtmlSource


class UruguayISBNSource(CerlalcHtmlSource):
    source_name = "uruguay_isbn"
    base_url = "https://www.bibna.gub.uy/isbn/catalogo.php"
