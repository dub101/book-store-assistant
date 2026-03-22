# Book Store Assistant

Book Store Assistant is currently focused on Stage 1 of the split pipeline:

- input: a CSV with ISBNs
- output 1: an upload-ready Excel workbook
- output 2: a JSONL handoff for Stage 2
- optional output 3: a compact review workbook for rows that still need human attention

The active Stage 1 upload columns are:

- `ISBN`
- `Title`
- `Subtitle`
- `Author`
- `Editorial`
- `Publisher`

Stage 1 does not generate synopsis or subject data anymore.
Those belong to the later Stage 2 pipeline that will consume the JSONL handoff.

## Goal

Stage 1 is optimized for bibliographic correctness first and throughput second.

The active runtime does this:

1. Read and normalize ISBNs from CSV.
2. Fetch bibliographic metadata from deterministic sources.
3. Run a grounded web-retrieval pass when Stage 1 fields are still incomplete.
4. Use exact-ISBN retailer and publisher web lookup to confirm or fill remaining gaps.
5. Resolve editorial and publisher identity.
6. Build a candidate upload row with:
   - `ISBN`
   - `Title`
   - `Subtitle`
   - `Author`
   - `Editorial`
   - `Publisher`
7. Run an LLM validator on the candidate row.
8. Send accepted rows to the upload workbook.
9. Send rejected or incomplete rows to the review workbook.
10. Persist all per-row Stage 1 results to JSONL for Stage 2.

Current rule of thumb:

- deterministic sources remain the first pass
- grounded web retrieval may propose Stage 1 fields, but later retailer/publisher checks still run
- the final upload row still goes through validation before acceptance

## Current Runtime

The main orchestration entry point is:

- `src/book_store_assistant/pipeline/service.py`

The active CLI entry point is:

- `src/book_store_assistant/cli.py`

Main Stage 1 components:

- `src/book_store_assistant/sources/staged.py`
  - staged metadata fetch from BNE, Open Library, and Google Books
- `src/book_store_assistant/sources/web_search.py`
  - grounded web retrieval and evidence-backed extraction for incomplete rows
- `src/book_store_assistant/sources/retailer_pages.py`
  - exact-ISBN retailer lookup for missing bibliographic fields
- `src/book_store_assistant/sources/publisher_pages.py`
  - publisher page lookup when bibliographic fields are still incomplete
- `src/book_store_assistant/sources/publisher_discovery.py`
  - exact-ISBN discovery pass for remaining incomplete rows
- `src/book_store_assistant/publisher_identity/service.py`
  - editorial/publisher normalization
- `src/book_store_assistant/bibliographic/resolution.py`
  - Stage 1 candidate construction and acceptance/review routing
- `src/book_store_assistant/resolution/openai_bibliographic_validator.py`
  - LLM validation for upload rows only
- `src/book_store_assistant/bibliographic/export.py`
  - upload Excel, review Excel, and JSONL handoff export

Compact flow:

`Input -> Staged Fetch -> Grounded Web Retrieval -> Retailer / Publisher Checks -> Publisher Identity -> Candidate Row -> LLM Validation -> Upload/Review/Handoff`

## Outputs

### Upload Workbook

Sheet name: `Upload`

Columns:

- `ISBN`
- `Title`
- `Subtitle`
- `Author`
- `Editorial`
- `Publisher`

### Review Workbook

Sheet name: `Review`

Columns:

- `ISBN`
- `Title`
- `Subtitle`
- `Author`
- `Editorial`
- `Publisher`
- `Status`
- `ReasonCode`
- `ValidatorConfidence`
- `ReviewNote`

The review workbook is intentionally minimal.
Detailed provenance and diagnostics live in the JSONL handoff, not in the spreadsheet.

### JSONL Handoff

The JSONL handoff contains one serialized Stage 1 result per line.
It preserves:

- source record data
- publisher identity
- validator assessment
- accepted candidate row when available
- reason codes and review details
- per-stage diagnostics and a path summary of where the row improved

This handoff is the intended input boundary for Stage 2.

## No Cache Policy

The active Stage 1 runtime no longer uses cache files.

Removed from the active path:

- staged fetch cache
- retailer page cache
- publisher page cache
- hidden intermediate stage snapshots

Runs now reflect live source behavior instead of stale cached data.

## Development

Create the virtual environment:

```bash
python -m venv .venv
```

Install dependencies:

```bash
.venv/bin/pip install -e ".[dev]"
```

Run targeted tests for the current Stage 1 path:

```bash
.venv/bin/pytest tests/test_bibliographic_export.py tests/test_resolution_service.py tests/test_pipeline_service.py tests/test_cli.py
```

Run lint and type checks when needed:

```bash
.venv/bin/ruff check .
.venv/bin/mypy src
```

## Configuration

Non-secret operational settings can live in `bsa.toml`.
An example file is included as `bsa.toml.example`.

Configuration precedence:

1. explicit CLI arguments
2. environment variables
3. `bsa.toml`
4. code defaults

Typical `bsa.toml` settings:

```toml
input_dir = "data/input"
output_dir = "data/output"
publisher_page_lookup_enabled = true
retailer_page_lookup_enabled = true
publisher_page_timeout_seconds = 6.0
retailer_page_timeout_seconds = 4.0
publisher_page_max_retries = 0
retailer_page_max_retries = 0
publisher_page_backoff_seconds = 0.5
retailer_page_backoff_seconds = 0.25
publisher_page_max_search_attempts_per_record = 8
publisher_page_max_fetch_attempts_per_record = 4
retailer_page_max_search_attempts_per_record = 6
retailer_page_max_fetch_attempts_per_record = 3
web_search_timeout_seconds = 10.0
web_search_max_pages_per_record = 4
web_search_max_search_attempts_per_record = 5
web_search_max_fetch_attempts_per_record = 4
source_request_pause_seconds = 0.5
open_library_batch_size = 25
request_timeout_seconds = 10.0
llm_record_validation_enabled = true
llm_record_validation_min_confidence = 0.85
```

Minimum AI environment variables:

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"
```

The app does not load `.env` files by itself.

Preferred helper on this machine:

```bash
bsa() {
  cd "$HOME/Documents/projects/pet_projects/book-store-assistant" || return
  OPENAI_API_KEY="$OPENAI_API_KEY_BOOK_STORE_ASSISTANT" \
  OPENAI_MODEL="gpt-4o-mini" \
  ./.venv/bin/python -m book_store_assistant.cli "$@"
}
```

`bsa` is the preferred way to run the project here because it maps the repo-specific OpenAI key into `OPENAI_API_KEY` before launching the CLI.

## CLI

Preferred invocation:

```bash
bsa data/input/sample_1.csv --output data/output/upload.xlsx --review-output data/output/review.xlsx --handoff-output data/output/handoff.jsonl
```

Equivalent direct invocation:

```bash
.venv/bin/python -m book_store_assistant.cli data/input/sample_1.csv --output data/output/upload.xlsx --review-output data/output/review.xlsx --handoff-output data/output/handoff.jsonl
```

Current CLI behavior:

- prints valid and invalid input counts
- prints invalid raw input values
- prints fetched, resolved, and unresolved counts
- prints aggregated source issue-code counts
- warns explicitly when Google Books rate limiting is detected
- prints unresolved source counts
- prints unresolved reason-code counts
- logs per-ISBN fetch outcomes
- logs per-ISBN final resolution status

If `--output` is provided and `--handoff-output` is omitted, the CLI derives a handoff path automatically by appending `.handoff.jsonl` to the upload workbook stem.

## Notes

- `Editorial` and `Publisher` are exported as separate columns in Stage 1.
- When only one trusted publishing name is available, the validator is allowed to accept the same value in both fields.
- Stage 2 is intentionally not part of the active runtime yet.
