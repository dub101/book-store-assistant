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
- CLI fetch progress and per-ISBN fetch outcome logs
- Test suite with coverage reporting

Pending:
- Real subject catalog tuning from bookstore feedback
- More robust subject heuristics beyond conservative embedded matching
- Confidence scoring and source precedence policy
- Better CLI workflow and example input/output files
- Spanish-first source expansion research, starting with Cerlalc feasibility

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
- SubjectCode
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
- SubjectCode
- SubjectType
- Categories
- CoverURL
- Synopsis
- FieldSources
- ReasonCodes
- ReviewDetails

## Rules

- ISBN, Title, Author, Editorial, Synopsis, Subject, and SubjectCode are mandatory for resolved output
- Subtitle is included only when relevant
- Synopsis must be in Spanish
- If the available synopsis is non-Spanish, the row is sent to review instead of generating translated or bilingual text
- Subject must be selected from the bookstore's internal list
- Resolved export includes both the subject description and the internal subject code
- Cover image is provided as a URL
- Metadata should remain factual; the tool should not invent book data

## Subject Catalog Format

The reference subject file lives at `data/reference/subjects.tsv`.

Supported formats:
- Plain canonical subject: `Narrativa`
- Canonical subject with aliases: `Historia | Historical | Historia universal`
- Tabular catalog with `Subject`, `Description`, and `Subject_Type` columns

Rules:
- The first value is the canonical bookstore subject used in exports
- Additional `|`-separated values are accepted aliases for matching
- Blank lines and `#` comments are ignored

Current pipeline note:
- The ISBN import pipeline currently resolves subjects only against book subject types (`L0`)
- Non-book subject types such as `P0` are preserved in the catalog for future use, but are excluded from subject resolution in the current workflow
- Resolved export keeps `Subject` as the human-readable description and adds `SubjectCode` for Geslib mapping

Example:
```text
# canonical | aliases
Narrativa | Ficcion | Fiction | Novel
Historia | Historical | Historia universal
Infantil | Juvenile | Juvenile Fiction
```

Tabular example:
```text
Subject	Description	Subject_Type
13	FICCION	L0
1402	HISTORIA	L0
22	PELUCHES Y TITERES	P0
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
- shows fetch progress during long runs
- logs per-ISBN fetch outcomes during consultation

## Geslib Import Workflow

Geslib import is currently treated as a column-mapping workflow rather than a fixed Excel template contract.

Recommended mapping for the resolved workbook:
- Map `ISBN` to the ISBN field in Geslib
- Map `Title`, `Subtitle`, `Author`, `Editorial`, and `Synopsis` to their corresponding metadata fields
- Map `Subject` when the Geslib importer expects the human-readable subject description
- Map `SubjectCode` when the Geslib importer expects the internal bookstore subject code
- Keep both `Subject` and `SubjectCode` in the export so the operator can choose the correct Geslib target during import

Current operator note:
- `Subject` is the bookstore subject description from the structured catalog
- `SubjectCode` is the internal code from the same catalog row
- `SubjectType` appears only in the review workbook for diagnosis and catalog verification

## Source Expansion Research

The next source investigation is Cerlalc because it is directly aligned with Spanish and Latin American book metadata.

See `docs/cerlalc_research.md` for the working feasibility note.

Current research goal:
- determine whether Cerlalc exposes a stable public search or record endpoint
- determine whether it can be integrated as a source without brittle scraping
- identify which fields are realistically available for enrichment:
  - title
  - author
  - editorial
  - synopsis
  - language
  - subject clues

Why this matters:
- recent real-batch testing showed low resolved yield
- the main blockers were missing synopsis and weak Spanish-language coverage
- Cerlalc is the most plausible next source to improve those outcomes

## Next Steps

1. Improve operator feedback during long runs.
   - keep the progress bar
   - add clearer per-ISBN final status such as `resolved` or `review`

2. Run a focused Cerlalc feasibility spike.
   - verify whether lookup by ISBN is stable
   - determine whether integration would use a public endpoint or brittle scraping
   - confirm which metadata fields are realistically available

3. Add a `CerlalcSource` adapter only if the lookup surface is stable.
   - start conservatively
   - prioritize title, editorial, language, synopsis, and subject clues

4. Re-run end-to-end acceptance testing on real ISBN batches.
   - compare resolved rate before and after the new source
   - inspect review rows to see whether synopsis coverage improves

## Project Structure
- `src/book_store_assistant/` application code
- `tests/` automated tests
- `data/input/` local input CSV files kept out of git except `.gitkeep`
- `data/output/` generated output files
- `data/reference/subjects.tsv` internal subject catalog
