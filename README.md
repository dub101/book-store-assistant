# Book Store Assistant

Python tool to transform a CSV of ISBNs into Geslib-ready Excel files with completed book metadata and a separate review file for unresolved rows.

## Current Status

Implemented:
- Python project scaffold
- CLI entry point
- ISBN normalization and validation
- CSV ingestion for ISBN files
- Structured pipeline result models
- Google Books source integration and payload parser
- Open Library source integration and payload parser
- Conservative multi-source merge for deterministic fields
- Field-level source provenance for merged metadata
- Batch fetch and batch resolution services
- Subject loading from a reference file
- Subject catalog aliases using `Canonical | Alias1 | Alias2` format
- Subject selection and subject resolution from source categories
- Structured unresolved reason codes and review details
- Synopsis presence and Spanish-language review rules
- Excel export for resolved records
- Excel export for unresolved review rows
- CLI support for export and review export
- Test suite with coverage reporting

Pending:
- Real subject catalog from the bookstore
- More robust subject heuristics beyond conservative embedded matching
- Exact Geslib import template validation
- Confidence scoring and source precedence policy
- Better CLI workflow and example input/output files

## Version 1 Scope

Input:
- CSV file with one ISBN per row

Output:
- Excel file ready for Geslib import
- Excel review file for unresolved rows

Resolved workbook columns:
- ISBN
- Title
- Subtitle
- Author
- Editorial
- Synopsis
- Subject
- CoverURL

Review workbook columns:
- ISBN
- Title
- Subtitle
- Author
- Editorial
- Source
- Language
- Subject
- Categories
- CoverURL
- Synopsis
- FieldSources
- ReasonCodes
- ReviewDetails

## Rules

- ISBN, Title, Author, Editorial, Synopsis, and Subject are mandatory for resolved output
- Subtitle is included only when relevant
- Synopsis must be in Spanish
- If the available synopsis is non-Spanish, the row is sent to review instead of generating translated or bilingual text
- Subject must be selected from the bookstore's internal list
- Cover image is provided as a URL
- Metadata should remain factual; the tool should not invent book data

## Subject Catalog Format

The reference subject file lives at `data/reference/subjects.txt`.

Supported formats:
- Plain canonical subject: `Narrativa`
- Canonical subject with aliases: `Historia | Historical | Historia universal`

Rules:
- The first value is the canonical bookstore subject used in exports
- Additional `|`-separated values are accepted aliases for matching
- Blank lines and `#` comments are ignored

Current pipeline note:
- The ISBN import pipeline currently resolves subjects only against book subject types (`L0`)
- Non-book subject types such as `P0` are preserved in the catalog for future use, but are excluded from subject resolution in the current workflow

Example:
```text
# canonical | aliases
Narrativa | Ficcion | Fiction | Novel
Historia | Historical | Historia universal
Infantil | Juvenile | Juvenile Fiction
```

## Development

Create the virtual environment:

```bash
python -m venv .venv
```

Install dependencies:
```bash
.venv/bin/pip install -e ".[dev]"
```

Run tests:
```bash
.venv/bin/pytest
```

## Current CLI

The current CLI reads ISBNs from a CSV file, fetches metadata, resolves valid records, and can export both resolved and unresolved rows.

Example:
```bash
.venv/bin/book-store-assistant data/input/isbns.csv --output data/output/books.xlsx --review-output data/output/review.xlsx
```

CLI summary behavior:
- prints valid and invalid input counts
- prints invalid raw input values
- prints fetched, resolved, and unresolved counts
- prints unresolved source counts
- prints unresolved reason-code counts

## Project Structure
- `src/book_store_assistant/` application code
- `tests/` automated tests
- `data/input/` input CSV files
- `data/output/` generated output files
- `data/reference/subjects.txt` internal subject catalog
