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
- Batch fetch and batch resolution services
- Subject loading from a reference file
- Subject selection and subject resolution from source categories
- Synopsis presence and formatting rules
- Excel export for resolved records
- Excel export for unresolved review rows
- CLI support for export and review export
- Test suite with coverage reporting

Pending:
- Real subject catalog from the bookstore
- Better subject matching beyond exact comparisons
- Proper bilingual synopsis generation/translation
- Multi-source retrieval strategy
- Confidence scoring and source precedence
- Exact Geslib import template validation
- Better CLI workflow and example input/output files

## Version 1 Scope

Input:
- CSV file with one ISBN per row

Output:
- Excel file ready for Geslib import
- Excel review file for unresolved rows

Target columns:
- ISBN
- Title
- Subtitle
- Author
- Editorial
- Synopsis
- Subject
- CoverURL

## Rules

- ISBN, Title, Author, Editorial, Synopsis, and Subject are mandatory
- Subtitle is included only when relevant
- Synopsis must be in Spanish
- If the book is in another language, synopsis must include Spanish first and then the original language
- Subject must be selected from the bookstore's internal list
- Cover image is provided as a URL

## Development

Create the virtual environment:

```bash
python -m venv .venv
```

Install dependencies
```bash
.venv/bin/pip install -e ".[dev]"
```

Run tests
```bash
.venv/bin/pytest
```

## Current CLI

The current CLI reads ISBNs from a CSV file, fetches metadata, resolves valid records, and can export both resolved and unresolved rows.

Example:
```bash
.venv/bin/book-store-assistant data/input/isbns.csv --output data/output/books.xlsx --review-output data/output/review.xlsx
```

## Project Structure
- src/book_store_assistant/ application code
- tests/ automated tests
- data/input/ input CSV files
- data/output/ generated output files
- data/reference/subjects.txt internal subject catalog