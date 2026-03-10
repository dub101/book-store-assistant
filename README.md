# Book Store Assistant

Book Store Assistant transforms a CSV of ISBNs into:
- a Geslib-ready Excel workbook for resolved books
- a review workbook for rows that still need manual attention

The project is optimized for trustworthy resolution rather than maximum yield. It prefers review over invention.

## Goal

The business goal is to automate bookstore intake while preserving metadata quality.

For a row to be resolved, the pipeline must produce:
- `ISBN`
- `Title`
- `Author`
- `Editorial`
- `Synopsis`
- `Subject`
- `SubjectCode`

Additional rules:
- `Synopsis` must be in Spanish
- `Subject` must come from the internal bookstore catalog
- metadata must remain factual
- unresolved or unsafe rows go to review rather than being guessed

## Execution Modes

The application supports two modes:

- `rules-only`
  - deterministic resolution only
  - no AI synopsis generation
  - non-Spanish or missing synopsis goes to review

- `ai-enriched`
  - runs the same deterministic pipeline first
  - collects grounded evidence from trusted source data and trusted source pages
  - may generate a Spanish synopsis only when evidence is sufficient
  - must not make outcomes worse than `rules-only`

Current AI behavior is additive:
- existing acceptable synopsis data is preserved
- AI is only used to fill missing or unusable synopsis fields
- rejected or weak generations stay visible in diagnostics and review output

## Pipeline Flow

The main runtime flow is:

1. Read ISBN inputs from CSV.
2. Normalize and validate ISBNs.
3. Fetch source metadata through source adapters.
4. Merge source records conservatively and preserve field provenance.
5. Optionally enrich synopsis data in `ai-enriched`.
6. Resolve business-required fields.
7. Split into resolved rows and review rows.
8. Export workbook outputs.

The main orchestration entry point is `process_isbn_file()` in `src/book_store_assistant/pipeline/service.py`.

## Architecture

The codebase follows a layered, pipeline-oriented structure.

Core layers:
- `pipeline/`
  - orchestration and process-level contracts
  - coordinates input, fetch, enrichment, resolution, and export
- `sources/`
  - metadata source ports/adapters
  - provider-specific fetchers, payload parsers, merge logic, and source issue tracking
- `enrichment/`
  - evidence collection and synopsis generation
  - provider wiring for AI-backed enrichment
- `resolution/`
  - business rules for synopsis acceptance, subject resolution, and required-field checks
- `export/`
  - workbook schemas, row builders, and Excel writing
- `validation/`
  - export validation and record-level checks

Shared support modules:
- `config.py`
  - application configuration defaults
- `models.py`
  - resolved output model
- `subject_loader.py`, `subject_mapping.py`, `subject_selection.py`
  - bookstore subject catalog loading and matching
- `isbn.py`
  - normalization and validity rules for ISBNs

Architectural intent:
- schema-first: intermediate results are explicit models
- ports/adapters: external sources stay isolated from core resolution logic
- rules-first: deterministic metadata and business rules take priority
- additive enrichment: AI is used only where it can be grounded and safely constrained

## Repo Map

Important package entry points:
- `src/book_store_assistant/cli.py`
  - Typer CLI entry point
- `src/book_store_assistant/pipeline/service.py`
  - end-to-end orchestration
- `src/book_store_assistant/resolution/books.py`
  - required-field resolution and review routing
- `src/book_store_assistant/sources/google_books.py`
  - Google Books adapter with retry/backoff
- `src/book_store_assistant/sources/open_library.py`
  - Open Library adapter
- `src/book_store_assistant/export/schema.py`
  - workbook column contracts
- `data/reference/subjects.tsv`
  - internal subject catalog

## Current Backbone Capabilities

Implemented:
- project scaffold with `pytest`, `ruff`, and `mypy`
- ISBN normalization and validation
- CSV ingestion
- structured pipeline result models
- Google Books and Open Library source adapters
- conservative multi-source merge with field provenance
- structured fetch issue codes
- Google Books retry/backoff for HTTP `429`
- deterministic resolution and unresolved/review routing
- dual execution modes: `rules-only` and `ai-enriched`
- grounded evidence collection for AI synopsis generation
- resolved and review Excel export
- internal subject catalog loading and alias-aware matching
- CLI progress, status summaries, and degraded-source warnings

Still intentionally out of scope for the backbone:
- maximizing yield through many more sources
- broad subject taxonomy expansion beyond curated internal aliases
- aggressive heuristic guessing of missing metadata

## Output Contracts

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

## Subject Catalog Format

The reference subject file lives at `data/reference/subjects.tsv`.

Supported formats:
- plain canonical subject: `Narrativa`
- canonical subject with aliases: `Historia | Historical | Historia universal`
- tabular catalog with `Subject`, `Description`, `Subject_Type`, and optional `Aliases`

Rules:
- the canonical export value is the subject `Description`
- `Subject` in the resolved workbook is the human-readable bookstore description
- `SubjectCode` is the internal bookstore code from the same catalog row
- optional aliases are accepted for matching but are not exported as resolved subject values
- blank lines and `#` comments are ignored
- the current pipeline resolves only book subject types (`L0`)
- non-book subject types such as `P0` remain in the catalog but are excluded from current subject resolution

Legacy example:
```text
# canonical | aliases
Narrativa | Ficcion | Fiction | Novel
Historia | Historical | Historia universal
Infantil | Juvenile | Juvenile Fiction
```

Tabular example:
```text
Subject	Description	Subject_Type	Aliases
13	FICCION	L0	Fiction | Novel
1301	LITERATURA Y NOVELA	L0	Literature | Romance literature
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

## CLI

The CLI reads ISBNs from a CSV file, runs the pipeline, and can export both resolved and review outputs.

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

## How To Extend The Project

To add a new metadata source:
- create a new adapter in `src/book_store_assistant/sources/`
- keep provider-specific parsing inside that adapter or its parser module
- return structured `FetchResult` data, including issue codes on failures
- add the source in `src/book_store_assistant/sources/defaults.py`
- cover it with focused adapter/parser tests

To change business rules:
- start in `src/book_store_assistant/resolution/`
- keep deterministic business decisions there rather than in source adapters or the CLI

To change workbook columns:
- update `src/book_store_assistant/export/schema.py`
- update row builders in `src/book_store_assistant/export/rows.py`
- update export validation and tests together

To evolve AI enrichment:
- keep evidence gathering in `src/book_store_assistant/enrichment/evidence.py`
- keep generation/provider concerns in `src/book_store_assistant/enrichment/`
- preserve the rules-first, grounded-only behavior

## Quality Gate

The standard local validation flow is:

```bash
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest
```

For day-to-day work:
- make changes in coherent slices
- stop at stable checkpoints
- prefer focused tests while iterating
- run the full quality gate before committing

## Known Boundaries

This backbone is intentionally conservative.

Current limitations:
- source availability still affects yield
- synopsis generation depends on grounded evidence coverage
- subject matching is limited to the internal catalog and its curated aliases
- the system prefers review over speculative resolution

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
