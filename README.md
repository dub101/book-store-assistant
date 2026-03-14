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
  - may generate a standardized Spanish synopsis when evidence is sufficient
  - must not make outcomes worse than `rules-only`

Current AI behavior:
- synopsis generation is grounded by collected evidence only
- output synopsis text may be standardized in `ai-enriched` when evidence is sufficient
- subject mapping remains constrained to exact values from the internal catalog
- rejected or weak generations stay visible in diagnostics and review output

## Pipeline Flow

The main runtime flow is:

1. Read ISBN inputs from CSV.
2. Normalize and validate ISBNs.
3. Read cached fetch results.
4. Query BNE for rows still missing required metadata when enabled.
5. Batch query Open Library for rows still missing required metadata.
6. Query Google Books one by one for rows still missing required metadata or synopsis support.
7. Query trusted publisher pages for ISBN-confirmed metadata upgrades when helpful.
8. Query trusted retailer pages for missing `editorial` when core sources still leave it blank.
9. Re-run publisher-page lookup for rows whose `editorial` was unlocked by retailer fallback.
10. Resolve publisher identity separately from edition metadata and attach provenance.
11. Merge source records conservatively with field-level confidence and provenance.
12. Optionally enrich synopsis data in `ai-enriched`.
13. Resolve business-required fields.
14. Split into resolved rows and review rows.
15. Export workbook outputs.

The main orchestration entry point is `process_isbn_file()` in `src/book_store_assistant/pipeline/service.py`.

## Architecture

The codebase follows a layered, pipeline-oriented structure.

Core layers:
- `pipeline/`
  - orchestration and process-level contracts
  - coordinates input, fetch, enrichment, resolution, and export
- `publisher_identity/`
  - publisher/imprint resolution separated from edition metadata resolution
  - stores publisher provenance, confidence, and matching method
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
- auditability-first: chosen metadata stays explainable through field provenance, confidence, and raw payload retention

## Repo Map

Important package entry points:
- `src/book_store_assistant/cli.py`
  - Typer CLI entry point
- `src/book_store_assistant/pipeline/service.py`
  - end-to-end orchestration
- `src/book_store_assistant/publisher_identity/service.py`
  - publisher identity resolution and attachment
- `src/book_store_assistant/resolution/books.py`
  - required-field resolution and review routing
- `src/book_store_assistant/sources/bne.py`
  - BNE SRU adapter for Spain-first metadata lookup
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
- BNE, Google Books, and Open Library source adapters
- staged fetch flow: cache -> BNE -> Open Library -> Google Books -> publisher pages -> retailer editorial fallback -> targeted publisher re-pass
- JSONL intermediates for staged fetch results
- successful fetch-result caching
- separate publisher identity resolution with provenance and confidence
- conservative multi-source merge with field provenance and field-level confidence
- structured fetch issue codes
- Google Books retry/backoff for HTTP `429`
- publisher-page lookup with ISBN-confirmed page parsing
- negative caching and retry/backoff for publisher-page search/fetch
- retailer-page fallback for missing `editorial`
- targeted second publisher-page pass after retailer `editorial` recovery
- deterministic resolution and unresolved/review routing
- dual execution modes: `rules-only` and `ai-enriched`
- grounded evidence collection for AI synopsis generation
- Google Books synopsis fallback through `searchInfo.textSnippet` when `description` is absent
- constrained AI subject mapping to internal catalog values only
- stronger deterministic subject resolution from controlled provider terms before LLM fallback
- generated synopsis rejection when cited evidence is not descriptively grounded
- resolved and review Excel export
- raw upstream payload retention in fetch results and review output for auditing
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
- GeneratedSynopsisText
- GeneratedSynopsisRaw
- RawSourcePayload
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

## Configuration

Non-secret operational settings can live in `bsa.toml`.
An example file is included as `bsa.toml.example`.

Configuration precedence:
1. explicit CLI/runtime arguments
2. environment variables
3. `bsa.toml`
4. code defaults

Recommended:
- keep non-secret pipeline settings in `bsa.toml`
- keep secrets such as `OPENAI_API_KEY` in the shell environment

Typical `bsa.toml` settings:
```bash
input_dir = "data/input"
output_dir = "data/output"
intermediate_dir = "data/intermediate"
source_cache_dir = "data/cache/fetch"
publisher_page_cache_dir = "data/cache/publisher_pages"
source_cache_enabled = true
bne_lookup_enabled = true
bne_sru_base_url = "https://catalogo.bne.es/view/sru/34BNE_INST"
publisher_page_cache_enabled = true
publisher_page_lookup_enabled = true
retailer_page_lookup_enabled = true
publisher_page_negative_cache_ttl_seconds = 21600
publisher_page_timeout_seconds = 3.0
publisher_page_max_retries = 2
publisher_page_backoff_seconds = 0.5
request_timeout_seconds = 10.0
source_request_pause_seconds = 0.5
open_library_batch_size = 25
execution_mode = "rules-only"
llm_subject_mapping_enabled = true
llm_subject_mapping_min_confidence = 0.85
```

Secrets and provider settings still come from the process environment.

Minimum AI variables:
```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"
```

The app does not load `.env` files by itself.

Preferred way to run the project:
- use the `bsa` shell helper
- this repo's shell helper maps `OPENAI_API_KEY_BOOK_STORE_ASSISTANT` to `OPENAI_API_KEY` before launching the CLI
- this avoids the common mistake where direct `python -m ...` runs miss the API key and silently degrade `ai-enriched` mode

Recommended helper:
```bash
bsa() {
  cd "$HOME/Documents/projects/pet_projects/book-store-assistant" || return
  OPENAI_API_KEY="$OPENAI_API_KEY_BOOK_STORE_ASSISTANT" \
  OPENAI_MODEL="${OPENAI_MODEL:-gpt-4o-mini}" \
  ./.venv/bin/python -m book_store_assistant.cli "$@"
}
```

Important:
- `bsa.toml` is optional and intended for non-secret settings
- process environment overrides `bsa.toml`
- values stored in `.env` are ignored unless you export them into the shell yourself
- if you do not use `bsa`, export `OPENAI_API_KEY` in the same shell or pass it inline when invoking the CLI
- publisher-page and retailer-page lookup are enabled by default in normal runs
- page lookup can be disabled with `BSA_PUBLISHER_PAGE_LOOKUP_ENABLED=0` and `BSA_RETAILER_PAGE_LOOKUP_ENABLED=0`
- cache TTL, retry/backoff, and timeout remain configurable independently of those lookup toggles

## Current Caveats

- BNE, Open Library, Google Books, publisher search, and retailer search are upstream-dependent and may degrade with timeouts or HTTP `403`/`503`
- publisher discovery is intentionally conservative and only trusts pages that explicitly contain the target ISBN
- retailer fallback currently exists to recover missing `editorial`; it is not yet a broad metadata fallback for title/author/synopsis
- DuckDuckGo HTML search is currently opportunistic, not a guaranteed backbone source
- page-lookup runtime can still be dominated by repeated external search failures before the pipeline even reaches a product page URL
- output file names passed to the CLI should generally be unsuffixed, for example `sample_3_books.xlsx`
- running `./.venv/bin/python -m book_store_assistant.cli ...` directly will not see `OPENAI_API_KEY_BOOK_STORE_ASSISTANT` unless you export `OPENAI_API_KEY` in that shell
- using the `bsa` helper avoids that mismatch

## CLI

The CLI reads ISBNs from a CSV file, runs the pipeline, and can export both resolved and review outputs.

Recommended invocation:
```bash
bsa data/input/sample_1.csv --output data/output/books.xlsx --review-output data/output/review.xlsx
```

Recommended AI-enriched invocation:
```bash
bsa data/input/sample_1.csv --mode ai-enriched --output data/output/books.xlsx --review-output data/output/review.xlsx
```

Equivalent direct CLI form:
```bash
.venv/bin/book-store-assistant data/input/sample_1.csv --mode ai-enriched --output data/output/books.xlsx --review-output data/output/review.xlsx
```

Equivalent module form:
```bash
OPENAI_API_KEY="$OPENAI_API_KEY_BOOK_STORE_ASSISTANT" \
OPENAI_MODEL="gpt-4o-mini" \
.venv/bin/python -m book_store_assistant.cli data/input/sample_1.csv --mode ai-enriched --output data/output/books.xlsx --review-output data/output/review.xlsx
```

Direct invocation note:
- `bsa` is the safest default because it supplies the project-specific OpenAI key mapping automatically
- direct `.venv/bin/book-store-assistant` and `.venv/bin/python -m ...` invocations are fine only when `OPENAI_API_KEY` is already exported in that shell

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
- rules-only mode now continues to Google Books when synopsis is still missing, even if Open Library already supplied title/author/editorial/categories
- when `editorial` is still missing after core sources and the first publisher pass, the pipeline now tries selected retailer pages and then re-runs publisher lookup for just the newly unlocked rows
- retailer-derived `editorial` is kept as lower-confidence provenance than official publisher-page data
- source review rows now retain raw upstream payload text for audit and debugging

## Demo Run

For a quick demo, use the smaller tracked batch:

```bash
bsa data/input/sample_1.csv --mode ai-enriched --output data/output/books.xlsx --review-output data/output/review.xlsx
```

For a larger operator-style demo batch, use:

```bash
bsa data/input/sample_2.csv --mode ai-enriched --output data/output/books.xlsx --review-output data/output/review.xlsx
```

If you do not want to use the shell helper:

```bash
OPENAI_API_KEY="$OPENAI_API_KEY_BOOK_STORE_ASSISTANT" \
OPENAI_MODEL="gpt-4o-mini" \
./.venv/bin/python -m book_store_assistant.cli data/input/sample_2.csv --mode ai-enriched --output data/output/books.xlsx --review-output data/output/review.xlsx
```

Expected demo outcome:
- the CLI prints fetch progress, enrichment progress, per-ISBN enrichment/resolution statuses, source issue-code counts, and unresolved reason counts
- resolved rows are written to `data/output/books.ai-enriched.xlsx`
- unresolved rows are written to `data/output/review.ai-enriched.xlsx`

## Operator Workflow

Recommended operator flow:

1. Start with `sample_1.csv` for a quick smoke run or use a fresh ISBN file in `data/input/`.
2. Run `ai-enriched` mode when you want the best safe synopsis coverage.
3. Check the CLI summary for:
   - source issue codes
   - Google Books rate-limit warnings
   - unresolved reason counts
4. Review `books.*.xlsx` for resolved rows ready for Geslib import.
5. Review `review.*.xlsx` for unresolved rows, source diagnostics, and enrichment diagnostics.

Input file hygiene:
- tracked repo fixtures live as `sample_*.csv`
- ad hoc operator files in `data/input/` remain ignored by git unless explicitly promoted to tracked samples

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

## Contributor Workflow

Recommended contributor loop:

1. Check `git status --short --branch`.
2. Read the affected code path before editing.
3. Make one coherent slice at a time.
4. Run focused tests while iterating.
5. Run the full quality gate before committing.
6. Keep commits split by concern:
   - runtime behavior
   - tests
   - docs when possible

Useful local commands:

```bash
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest
```

Sample-batch regression tests:

```bash
.venv/bin/pytest tests/test_sample_batch_regressions.py
```

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
- `GeneratedSynopsisText` and `GeneratedSynopsisRaw` show the attempted AI synopsis and raw model output when generation was rejected
- `EvidenceOrigins` shows whether evidence came from direct source metadata, structured provider page data, or scraped provider page text
- `RawSourcePayload` shows the original upstream payload captured for the unresolved row

## Optional Future Work

The backbone is designed so more trusted sources can be added later without restructuring the core pipeline.

Examples:
- trusted publisher pages such as Planeta
- deferred bibliographic adapters such as Cerlalc where they materially improve coverage
- additional review diagnostics informed by real operator use

Current recommendation:
- treat source expansion as optional follow-on work
- preserve the current rules-first, adapter-based design when adding new providers

## Project Structure
- `src/book_store_assistant/` application code
- `tests/` automated tests
- `data/input/` tracked sample CSVs plus ignored ad hoc local input files
- `data/output/` generated output files
- `data/reference/subjects.tsv` internal subject catalog
