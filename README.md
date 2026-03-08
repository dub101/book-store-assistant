# Book Store Assistant

Python tool to transform a CSV of ISBNs into a Geslib-ready Excel file with completed book metadata.

## Current Status

Implemented:
- Python project scaffold
- CLI entry point
- ISBN normalization and validation
- CSV ingestion for ISBN files
- Structured pipeline input result model
- Google Books source integration and payload parser
- Initial source and resolution models
- Basic validation layer
- Initial test suite

Pending:
- Real end-to-end metadata pipeline
- Multi-source retrieval strategy
- Subject classification from the bookstore's internal list
- Synopsis generation/translation rules
- Excel export implementation
- Review/reporting flow for incomplete or low-confidence rows

## Version 1 Scope

Input:
- CSV file with one ISBN per row

Output:
- Excel file ready for Geslib import

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

Install dependencies:
```bash
.venv/bin/pip install -e ".[dev]"
```

Run tests:
```bash
.venv/bin/pytest
```
## Current CLI
The current CLI validates ISBN rows from a CSV file and reports valid and invalid counts.
Example:
```bash
.venv/bin/book-store-assistant data/input/isbns.csv
```
## Project Structure
- src/book_store_assistant/ application code
- tests/ automated tests
- data/input/ input CSV files
- data/output/ generated output files