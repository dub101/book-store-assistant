from book_store_assistant.pipeline.contracts import ISBNInput
from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.results import FetchResult


def fetch_all(source: MetadataSource, inputs: list[ISBNInput]) -> list[FetchResult]:
    return [source.fetch(item.isbn) for item in inputs]
