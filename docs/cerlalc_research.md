# Cerlalc Research

## Goal

Evaluate whether Cerlalc is a viable metadata source for Spanish and Latin American books in the ISBN ingestion pipeline.

## Why Cerlalc

Recent end-to-end testing showed:
- low resolved yield on real ISBN batches
- frequent missing synopsis
- weak Spanish-language metadata coverage

Cerlalc is a promising next source because it is closely tied to ISBN and publishing data in Latin America.

## Questions To Answer

1. Does Cerlalc expose a stable public search endpoint?
2. Does it expose a public record endpoint that can be queried by ISBN?
3. Is there a documented API, or would integration depend on HTML scraping?
4. Which metadata fields are realistically available?
5. Are there usage or legal constraints that would make integration unsafe?

## Known Entry Points

- ISBN program page:
  - https://cerlalc.org/isbn/
- Historical Latin American ISBN catalog:
  - https://cerlalc.org/catalogo-historico-de-titulos-con-isbn-de-america-latina/
- Example record page:
  - https://cerlalc.org/pt-br/rilvi/base-de-datos-18971/

Current observations:
- Cerlalc is clearly relevant as a domain source.
- A searchable catalog appears to exist.
- Individual record pages expose useful bibliographic metadata.
- A clearly documented public API has not yet been confirmed.
- Adapter work should wait until the search and record surface is verified as stable enough.

## Probe Findings

The manual probe established the following:
- the plain WordPress search path using `?s=<isbn>` is not useful for metadata lookup
- those pages resolve to generic site search pages and can return `search-no-results`
- a dedicated catalog page exists and uses a custom `rilvi` template plus the `cerlalc-plugin-2018` plugin
- stable-looking `rilvi/...` record pages exist and appear to expose bibliographic fields
- a clean public ISBN lookup endpoint was not confirmed from the catalog page surface

Observed likely-available fields from record pages:
- title
- ISBN
- editorial
- language
- subject or materia clues

Observed likely gap:
- synopsis does not appear to be a strong or reliable field on the record pages we inspected

## Desired Metadata

Highest-value fields for the current pipeline:
- title
- author
- editorial
- synopsis
- language
- subject or category clues
- cover image URL, if available

## Decision Criteria

Proceed with integration only if at least one of these is true:
- stable public API
- stable and simple public search endpoint with predictable record pages

Do not proceed directly to production integration if:
- access depends on brittle HTML scraping
- anti-bot measures or session-heavy flows are required
- field availability is too thin to improve current yield meaningfully

## Decision

Current decision: defer `CerlalcSource` for now.

Reasoning:
- Cerlalc may still be valuable as a secondary enrichment source later
- it does not currently present a confirmed clean ISBN lookup surface
- it is unlikely to address the primary current blocker, which is missing Spanish synopsis
- the next source search should prioritize synopsis coverage first, with Cerlalc kept as a secondary candidate

## Next Step

The Cerlalc spike is complete.

Next action:
- evaluate another Spanish-first metadata source with stronger chances of providing usable synopsis text
- keep Cerlalc on the backlog as a possible secondary enrichment source for bibliographic fields

## Planned Probe

The first probe should stay manual and low-risk.

Target:
- test lookup behavior for a single ISBN from a real batch

Desired outputs:
- final response URL
- HTTP status
- whether the ISBN appears in the returned page
- whether the page looks like a search result or a record page
- whether useful fields appear to be present:
  - title
  - author
  - editorial
  - language
  - synopsis
  - subject clues

Success condition:
- there is a repeatable ISBN-driven lookup path that returns stable, parseable pages

Failure condition:
- lookup depends on brittle navigation, session-heavy flows, or inconsistent pages

Outcome:
- failure for the simple public search path
- inconclusive but not strong enough for immediate adapter work on the dedicated catalog path
