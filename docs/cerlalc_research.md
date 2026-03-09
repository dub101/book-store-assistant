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

## Next Step

Perform a focused technical verification of Cerlalc search and record lookup behavior by ISBN, then decide whether to:
- add a `CerlalcSource` adapter
- defer Cerlalc and evaluate other Spanish-first sources

The goal of the spike is not to ship an adapter immediately. The goal is to answer whether Cerlalc can be integrated safely and maintainably within the current ports-and-adapters architecture.
