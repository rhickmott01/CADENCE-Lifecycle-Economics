# Architecture and ownership

Main CADENCE is a read-only upstream reference. This repository has no git submodule, runtime import, or write access to main CADENCE. Proposed flow:

1. CADENCE preprocessing provides ID-keyed asset, option, hazard and cost slices.
2. DuckDB reads immutable HAZUS Parquet partitions and builds versioned consequence lookups.
3. Approved mapping joins match HAZUS construction/terrain/age/region; mapping logic is **not** inferred here.
4. A verified CADENCE AEL adapter provides wind probability masses or equivalent annual expected consequence values.
5. Independent Polars functions calculate hypothetical replacement events and 30-year annual cash flows.
6. The economic comparison returns NPC and incremental NPV; CADENCE retains actual adoption and RUL state transitions.

No geospatial operations occur at simulation time. All future RUL transitions require an audited CADENCE-compatible adapter. Prefect is optional orchestration only.

## Source-code compatibility audit required

The main repository was not accessible to the code-execution environment when drafting this archive. Prior discussion mentioned an Alternative Analysis README and existing 25-year analysis, but **no actual source functions or commit SHA have been verified in this draft**. Do not assert regression equivalence until the real source and tests are inspected.
