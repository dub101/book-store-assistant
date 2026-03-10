# Book Store Assistant

Python tool to transform a CSV of ISBNs into Geslib-ready Excel files with completed
book metadata and a separate review file for unresolved rows.

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
- CLI final per-ISBN resolution status logs
- CLI source issue-code counts and Google Books rate-limit warnings
- Configurable Google Books retry/backoff for HTTP 429 responses
- Dual execution modes: `rules-only` and `ai-enriched`
- AI enrichment contracts, validation, and provider wiring
- OpenAI-backed synopsis generation adapter
- Trusted descriptive evidence collection from source synopsis fields
- Trusted page-description evidence extraction from source URLs
- Review export diagnostics for enrichment outcomes
- Test suite with coverage reporting

Pending:
- Real subject catalog tuning from bookstore feedback
- More robust subject heuristics beyond conservative embedded matching
- Real end-to-end yield tuning on live ISBN batches
- Broader descriptive evidence collection beyond current trusted source pages
- Optional "normalize all synopsis" mode for consistent tone and length
- Better CLI/docs examples and operator workflow polish

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
- SourceIssueCodes
- EnrichmentStatus
- EvidenceCount
- EvidenceOrigins
- GeneratedSynopsisFlags
- ReasonCodes
- ReviewDetails

## Rules

- ISBN, Title, Author, Editorial, Synopsis, Subject, and SubjectCode are mandatory for resolved output
- Subtitle is included only when relevant
- Synopsis must be in Spanish
- In `rules-only` mode, if the available synopsis is non-Spanish, the row is sent to review
- In `ai-enriched` mode, the pipeline may generate a Spanish synopsis only from grounded descriptive evidence
- If the AI pipeline does not have enough evidence, or the generated synopsis fails validation, the row stays in review
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

Run lint and type checks:
```bash
.venv/bin/ruff check .
.venv/bin/mypy
```

## Execution Modes

The application supports two execution modes:

- `rules-only`
  - current deterministic pipeline
  - no AI synopsis generation
  - preserves the original behavior of the project

- `ai-enriched`
  - runs the same base pipeline
  - collects descriptive evidence from trusted source fields and trusted source pages
  - may generate a Spanish synopsis through the AI enrichment path when evidence is sufficient
  - validates generated synopsis before allowing it into resolution

Current priority is `fill-missing` behavior:
- AI is used to fill missing or unusable synopsis fields when grounded evidence exists
- future normalization of all synopsis text for consistent tone/length is possible, but not yet implemented

## Environment Setup

The app reads AI configuration from the process environment.
It does not load `.env` files by itself.

Minimum variables:
```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"
```

If you prefer a shell helper, define one in `~/.bashrc` that exports the project-specific values and runs the repo CLI.

Recommended helper:
```bash
bsa() {
  cd "$HOME/Documents/projects/pet_projects/book-store-assistant" || return
  OPENAI_API_KEY="$OPENAI_API_KEY_BOOK_STORE_ASSISTANT" \
  OPENAI_MODEL="gpt-4o-mini" \
  ./.venv/bin/python -m book_store_assistant.cli "$@"
}
```

Important:
- the app reads process environment only
- values stored in `.env` are ignored unless you export them into the shell yourself
- running `./.venv/bin/python -m book_store_assistant.cli ...` directly will not see `OPENAI_API_KEY_BOOK_STORE_ASSISTANT` unless you export `OPENAI_API_KEY` in that shell
- using the `bsa` helper avoids that mismatch

## Current CLI

The current CLI reads ISBNs from a CSV file, fetches metadata, resolves valid records, and can export both resolved and unresolved rows.

Example:
```bash
.venv/bin/book-store-assistant data/input/isbns.csv --output data/output/books.xlsx --review-output data/output/review.xlsx
```

AI-enriched example:
```bash
.venv/bin/book-store-assistant data/input/client_isbns.csv --mode ai-enriched --output data/output/books.xlsx --review-output data/output/review.xlsx
```

Shell-helper example:
```bash
bsa data/input/client_isbns.csv --mode ai-enriched --output data/output/books.xlsx --review-output data/output/review.xlsx
```

Module form:
```bash
.venv/bin/python -m book_store_assistant.cli data/input/client_isbns.csv --mode ai-enriched --output data/output/books.xlsx --review-output data/output/review.xlsx
```

CLI summary behavior:
- prints valid and invalid input counts
- prints invalid raw input values
- prints fetched, resolved, and unresolved counts
- prints execution mode
- prints aggregated source issue-code counts
- warns explicitly when Google Books rate limiting is detected
- prints unresolved source counts
- prints unresolved reason-code counts
- shows fetch progress during long runs
- logs per-ISBN fetch outcomes during consultation
- logs per-ISBN enrichment outcomes in `ai-enriched` mode
- logs per-ISBN final resolution status

Output naming behavior:
- the CLI appends the execution mode to output filenames
- `--output data/output/books.xlsx --mode rules-only` writes `data/output/books.rules-only.xlsx`
- `--output data/output/books.xlsx --mode ai-enriched` writes `data/output/books.ai-enriched.xlsx`
- the same applies to review files

Current `ai-enriched` limitation:
- AI generation only happens when the pipeline can gather grounded descriptive evidence
- if no synopsis and no trusted source-page description are available, the row remains unresolved
- the current bottleneck is still evidence coverage, not model availability

Current source-reliability note:
- Google Books fetches now retry on HTTP 429 responses with exponential backoff
- if Google Books eventually succeeds after retries, the run still reports the rate-limit issue code in the CLI summary so operators can see upstream degradation

## Demo Run

For a real demo with the current sample file, use:

```bash
bsa data/input/client_isbns.csv --mode ai-enriched --output data/output/books.xlsx --review-output data/output/review.xlsx
```

If you do not want to use the shell helper:

```bash
OPENAI_API_KEY="$OPENAI_API_KEY_BOOK_STORE_ASSISTANT" \
OPENAI_MODEL="gpt-4o-mini" \
./.venv/bin/python -m book_store_assistant.cli data/input/client_isbns.csv --mode ai-enriched --output data/output/books.xlsx --review-output data/output/review.xlsx
```

Expected demo outcome:
- the CLI prints fetch progress, enrichment decisions, per-ISBN resolution statuses, source issue-code counts, and unresolved reason counts
- resolved rows are written to `data/output/books.ai-enriched.xlsx`
- unresolved rows are written to `data/output/review.ai-enriched.xlsx`

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
- `EnrichmentStatus` appears only in the review workbook for AI-enrichment diagnosis
- `EvidenceCount` shows how many evidence blocks were collected for that unresolved row
- `GeneratedSynopsisFlags` shows validation failures when a generated synopsis was rejected
- `EvidenceOrigins` shows whether evidence came from direct source metadata, structured provider page data, or scraped provider page text

## Source Expansion Research

The Cerlalc feasibility spike has been completed.

See `docs/cerlalc_research.md` for the working feasibility note.

Current conclusion:
- Cerlalc is relevant as a Spanish and Latin American bibliographic source
- the obvious public search path is not suitable for ISBN lookup
- stable-looking `rilvi` record pages exist, but a clean public lookup endpoint was not confirmed
- Cerlalc may still be useful later for title, editorial, language, and subject clues
- Cerlalc is not currently the best next source because it is unlikely to materially improve synopsis coverage

Why this matters:
- recent real-batch testing showed low resolved yield
- the main blockers were missing synopsis and weak Spanish-language coverage
- the next source should be selected primarily on its ability to improve Spanish synopsis availability

Planned probe workflow:
```bash
python scripts/probe_cerlalc.py 9786070728792
```

The probe established that Cerlalc should be treated as a deferred source candidate rather than the immediate next adapter.

## AI Enrichment Flow

Current AI-enriched flow:

1. Fetch and merge source metadata.
2. Collect trusted descriptive evidence from:
   - source synopsis/description fields
   - trusted source page descriptions from source URLs
3. Decide whether evidence is sufficient.
4. If configured, call the AI synopsis generator.
5. Validate generated synopsis:
   - must be Spanish
   - must meet minimum length
   - must reference supporting evidence
6. If valid, inject generated synopsis before resolution.
7. If invalid or unsupported, keep the row in review with diagnostics.

## Next Steps

1. Re-run end-to-end acceptance testing on real ISBN batches with `ai-enriched`.
2. Compare:
   - evidence-bearing rows
   - enrichment-applied rows
   - resolved yield vs `rules-only`
3. Expand trusted evidence collection for rows that still show `insufficient_evidence`.
4. Improve review diagnostics and operator workflow based on real output.
5. Revisit optional "normalize all synopsis" behavior later, after evidence coverage is strong enough.

## Project Structure
- `src/book_store_assistant/` application code
- `tests/` automated tests
- `data/input/` local input CSV files kept out of git except `.gitkeep`
- `data/output/` generated output files
- `data/reference/subjects.tsv` internal subject catalog
