from pathlib import Path

from book_store_assistant.sources.results import FetchResult


def export_fetch_results(results: list[FetchResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [result.model_dump_json() for result in results]
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def read_fetch_results(path: Path) -> list[FetchResult]:
    results: list[FetchResult] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        results.append(FetchResult.model_validate_json(stripped))

    return results
