from book_store_assistant.resolution.results import ResolutionResult


def collect_unresolved_results(results: list[ResolutionResult]) -> list[ResolutionResult]:
    return [result for result in results if result.record is None]
