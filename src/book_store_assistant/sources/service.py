from collections.abc import Callable

from book_store_assistant.pipeline.contracts import ISBNInput
from book_store_assistant.sources.base import MetadataSource
from book_store_assistant.sources.results import FetchResult

FetchStartCallback = Callable[[int, int, str], None]
FetchCompleteCallback = Callable[[int, int, FetchResult], None]


def fetch_all(
    source: MetadataSource,
    inputs: list[ISBNInput],
    on_fetch_start: FetchStartCallback | None = None,
    on_fetch_complete: FetchCompleteCallback | None = None,
) -> list[FetchResult]:
    fetch_results: list[FetchResult] = []
    total = len(inputs)

    for index, item in enumerate(inputs, start=1):
        if on_fetch_start is not None:
            on_fetch_start(index, total, item.isbn)

        result = source.fetch(item.isbn)
        fetch_results.append(result)

        if on_fetch_complete is not None:
            on_fetch_complete(index, total, result)

    return fetch_results
