# Book Store Assistant

Book Store Assistant is a bibliographic enrichment pipeline that transforms a CSV of ISBNs into upload-ready Excel workbooks for bookstore inventory systems.

## What It Does

1. Read and normalize ISBNs from CSV or Excel.
2. Fetch bibliographic metadata from a cascade of sources (cheapest/best-fit first):
   - **ISBNdb** — commercial API with ~99% coverage ($15/month)
   - **National ISBN agencies** — routed by ISBN prefix (BNE for Spain, Cámara Colombiana del Libro for Colombia, stubs for 11 other Latin American countries)
   - **Open Library** — free, batch-capable
   - **Google Books** — free, with retry on rate limiting
3. Fall back to **LLM web enrichment** (OpenAI Responses API with web search) only when deterministic sources cannot provide title, author, or editorial (~2% of rows).
4. Run an **LLM validator** on the candidate row to catch hallucinated or mismatched data.
5. Export accepted rows to an **upload workbook** and rejected/incomplete rows to a **review workbook**.
6. Persist all per-row results to a **JSONL handoff** for downstream processing.

## Upload Columns

- `ISBN`
- `Title`
- `Subtitle`
- `Author`
- `Editorial`

Synopsis, Subject, and SubjectCode are available in the JSONL handoff for Stage 2 but are not required for upload.

## Source Cascade

```
ISBNdb → National Agency (by ISBN prefix) → Open Library → Google Books → LLM (fallback only)
```

### ISBN Prefix Routing

The ISBN registration group (digits after the 978/979 prefix) maps to national agencies:

| Prefix | Country | Source |
|--------|---------|--------|
| 84 | Spain | BNE SRU |
| 607, 968, 970 | Mexico | Stub |
| 950, 987 | Argentina | Stub |
| 958 | Colombia | Cámara Colombiana del Libro |
| 956 | Chile | Stub |
| 85, 65 | Brazil | Stub |
| 612, 9972 | Peru | Stub |
| 9974 | Uruguay | Stub |
| 9978 | Ecuador | Stub |

Stub sources return gracefully with a `NOT_IMPLEMENTED` issue code. The routing infrastructure is in place for future implementation.

## Outputs

### Upload Workbook

Sheet: `Upload` — columns: ISBN, Title, Subtitle, Author, Editorial.

### Review Workbook

Sheet: `Review` — columns: ISBN, Title, Subtitle, Author, Editorial, Status, ReasonCode, ValidatorConfidence, ReviewNote.

### JSONL Handoff

One JSON object per line with source records, diagnostics, path summaries, and validation assessments. This is the input boundary for Stage 2.

## Desktop GUI

A tkinter-based desktop interface for librarians:

- File picker for CSV or Excel input
- Progress bar with per-ISBN status updates
- Outputs saved alongside the input file
- Spanish-language interface

Launch:

```bash
.venv/bin/book-store-assistant-gui
```

Or directly:

```bash
.venv/bin/python -m book_store_assistant.gui
```

## CLI

Preferred invocation (uses `bsa` shell function from `.bashrc`):

```bash
bsa data/input/sample_1.csv \
  --output data/output/sample_1_upload.xlsx \
  --review-output data/output/sample_1_review.xlsx \
  --handoff-output data/output/sample_1_handoff.jsonl
```

Direct invocation:

```bash
.venv/bin/python -m book_store_assistant.cli data/input/sample_1.csv \
  --output data/output/upload.xlsx \
  --review-output data/output/review.xlsx \
  --handoff-output data/output/handoff.jsonl
```

If `--output` is provided and `--handoff-output` is omitted, the CLI derives a handoff path automatically.

## Configuration

Non-secret settings live in `bsa.toml` (see `bsa.toml.example`).

Precedence: `BSA_*` environment variables > `bsa.toml` > code defaults.

### Required Environment Variables

```bash
export OPENAI_API_KEY="sk-..."       # For LLM enrichment and validation
export OPENAI_MODEL="gpt-4o-mini"    # Model for LLM calls
export ISBNDB_API_KEY="..."          # ISBNdb API key ($15/month Premium plan)
```

### Key Configuration Options

```toml
bne_lookup_enabled = true
isbndb_lookup_enabled = true
national_agency_routing_enabled = true
llm_enrichment_enabled = true
llm_record_validation_enabled = true
source_request_pause_seconds = 0.5
llm_enrichment_timeout_seconds = 60.0
llm_record_validation_min_confidence = 0.80
```

## Development

### Setup

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

### Tests

Tests are organized into unit and integration suites:

```bash
# Run all tests
.venv/bin/pytest tests/

# Run only unit tests
.venv/bin/pytest tests/unit/

# Run only integration tests
.venv/bin/pytest tests/integration/

# Run with coverage
.venv/bin/pytest tests/ --cov=book_store_assistant --cov-report=term-missing
```

**362 tests, 95% coverage** (GUI excluded from coverage — tkinter not testable in headless CI).

Unit tests (14 files): parsers, routing, confidence, cleaning, diagnostics, validation, providers.

Integration tests (18 files): sources with mocked HTTP, CLI flows, pipeline orchestration, export formats.

### Linting and Type Checking

```bash
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/
```

### Project Structure

```
src/book_store_assistant/
├── bibliographic/          # Resolution, export, models
│   ├── export.py           # Upload/review/handoff export
│   ├── models.py           # BibliographicRecord
│   └── resolution.py       # Candidate building, field cleaning
├── pipeline/               # Orchestration
│   ├── input.py            # ISBN CSV parsing
│   └── service.py          # Main pipeline entry point
├── resolution/             # Validation
│   ├── openai_bibliographic_validator.py
│   ├── providers.py        # Validator/enricher factory
│   └── synopsis_resolution.py
├── sources/                # Data sources
│   ├── bne.py              # BNE SRU (Spain)
│   ├── google_books.py     # Google Books API
│   ├── isbndb.py           # ISBNdb API
│   ├── isbn_routing.py     # ISBN prefix → national agency
│   ├── llm_enrichment.py   # OpenAI web search enrichment
│   ├── merge.py            # Source record merging
│   ├── national/           # National agency sources
│   │   ├── base.py         # Stub source
│   │   └── colombia.py     # Cámara Colombiana del Libro
│   ├── open_library.py     # Open Library API
│   └── staged.py           # Cascade orchestrator
├── cli.py                  # CLI entry point
├── config.py               # AppConfig with toml/env loading
├── gui.py                  # Desktop GUI (tkinter)
└── isbn.py                 # ISBN validation and prefix routing

tests/
├── unit/                   # 14 files — isolated function tests
└── integration/            # 18 files — multi-module tests with mocked I/O
```

## Performance

Benchmarked against 200 hand-curated ISBNs (8 themed batches of 25):

| Metric | Value |
|--------|-------|
| Upload rate | 199/200 (99.5%) |
| LLM fallback rate | 4/200 (2%) |
| Title accuracy | 92% |
| Author accuracy | 94% |
| Editorial accuracy | 74% |
| Cost per 200 ISBNs | ~$4.32 (was ~$20 before ISBNdb) |
| Time per 25 ISBNs | ~80 seconds |

ISBNdb provides 97% of all field values. LLM enrichment is only needed for ~2% of rows where no deterministic source has the data.

## Notes

- ISBNdb has a rate limit of 3 requests/second on the Premium plan. The pipeline uses 0.5s pauses and exponential backoff on 429s.
- BNE editorial values often include city prefixes ("[Barcelona], Debolsillo") — the pipeline strips these automatically.
- BNE descriptions that are catalog metadata (original titles, narrator credits, <80 chars) are filtered out.
- The LLM validator compares cleaned candidate values against cleaned source evidence to prevent false rejections from normalization differences.
