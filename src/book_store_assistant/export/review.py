from pathlib import Path

import openpyxl

from book_store_assistant.resolution.results import ResolutionResult


HEADERS = [
    "ISBN",
    "Title",
    "Subtitle",
    "Author",
    "Editorial",
    "Source",
    "Language",
    "Categories",
    "CoverURL",
    "Errors",
]


def export_review_rows(results: list[ResolutionResult], output_path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)

    for result in results:
        if result.record is not None:
            continue

        source_record = result.source_record
        sheet.append(
            [
                source_record.isbn if source_record is not None else None,
                source_record.title if source_record is not None else None,
                source_record.subtitle if source_record is not None else None,
                source_record.author if source_record is not None else None,
                source_record.editorial if source_record is not None else None,
                source_record.source_name if source_record is not None else None,
                source_record.language if source_record is not None else None,
                ", ".join(source_record.categories) if source_record is not None else None,
                str(source_record.cover_url) if source_record is not None and source_record.cover_url else None,
                "; ".join(result.errors),
            ]
        )

    workbook.save(output_path)
