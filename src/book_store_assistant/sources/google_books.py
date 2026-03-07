from book_store_assistant.sources.models import SourceBookRecord


class GoogleBooksSource:
    source_name = "google_books"

    def fetch(self, isbn: str) -> SourceBookRecord | None:
        """Fetch metadata for an ISBN from Google Books."""
        raise NotImplementedError("Google Books source is not implemented yet.")
