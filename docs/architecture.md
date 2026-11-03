# Architecture and ownership

Main CADENCE is a read-only upstream reference. This repository has no git submodule or direct in-process dependency on the CADENCE engine. An opt-in read-only subprocess bridge now reuses its disposal helper and material mapper; it does not execute stock-flow or adoption decisions. Proposed flow:

1. CADENCE preprocessing provides ID-keyed asset, option, hazard and cost slices.
2. DuckDB reads immutable HAZUS Parquet partitions and builds versioned consequence lookups.
3. Approved mapping joins match HAZUS construction/terrain/age/region; mapping logic is **not** inferred here.
4. A verified CADENCE AEL adapter provides wind probability masses or equivalent annual expected consequence values.
5. Independent Polars functions calculate hypothetical replacement events and 30-year annual cash flows.
6. The economic comparison returns NPC and incremental NPV; CADENCE retains actual adoption and RUL state transitions.

No geospatial operations occur at simulation time. All future RUL transitions require an audited CADENCE-compatible adapter. Prefect is optional orchestration only.

## Source-code compatibility

The initial archive lacked access to CADENCE. The subsequent local audit and HEAD references are recorded in [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md). Source inspection and direct disposal-function reuse do not establish equivalence of hazard integration, repair valuation, production RUL transitions, or terminal conventions. Those remain integration gates.
