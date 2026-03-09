from book_store_assistant.pipeline.contracts import ISBNInput
from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.results import FetchResult


def fetch_all(source: MetadataSource, inputs: list[ISBNInput]) -> list[FetchResult]:
    fetch_results: list[FetchResult] = []

    for item in inputs:
        fetch_results.append(source.fetch(item.isbn))

    return fetch_results
