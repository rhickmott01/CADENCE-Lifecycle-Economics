# CADENCE-Lifecycle-Economics

**Status: first-draft standalone repository, not yet integrated with the main CADENCE engine.**

This package independently evaluates roofing lifecycle alternatives while preserving CADENCE's ownership of actual stock-flow state and decision rules. It does **not** modify or import the original CADENCE repository.

## Implemented in draft 0.1

- Polars-vectorized deterministic replacement schedules for a fixed-EUL **pilot**.
- Straight-line terminal service value (with separate existing-roof basis).
- Annual real-dollar cost-stream assembly and discounted net present cost (NPC).
- Incremental NPV versus a caller-supplied `baseline` alternative.
- Strict, explicit five-measure HAZUS consequence units and monetization.
- Integration of **precomputed approved discrete hazard probability masses**; no independent return-period interpolation.
- DuckDB source partition inspection and five-measure consequence extraction.
- Read-only integration stubs and fail-closed material mapping validation.
- Write-once versioned Parquet output and deterministic run manifest.
- Focused synthetic tests.

## Not implemented / deliberately blocked

- CADENCE's exact AEL probability integration: **requires current source-code audit**. Do not substitute the discrete-mass pilot as a scientific equivalence claim.
- CADENCE production RUL/degradation transitions: **requires actual source-code contract**.
- Unapproved material-to-HAZUS proxies (including metal/tile): blocked.
- Vulnerability extrapolation beyond age 30: blocked by integration contract; this package never manufactures extra curves.
- Maintenance, salvage and debris cleanup prices: no invented defaults; caller must supply values or disable stream.
- BCR and payback: deferred until incremental benefit/cost classification is approved.
- Full automatic five-measure curve matching by construction/terrain: requires approved attribute mapping.
- Any CADENCE production installation or adoption decisions.

## Install

```bash
python -m pip install -e '.[dev]'
pytest -q
```

## Source extraction

```bash
python scripts/inspect_sources.py /path/to/output/iecc2021/3A/age_01
python scripts/build_consequence_lookup.py /path/to/output/iecc2021/3A/age_01 /path/to/new/version/curves.parquet
```

The exporter writes a **single partition** and preserves all source curve columns and the 41 wind-speed points. The original `curve_attributes_hu.parquet` remains the authoritative source of terrain/construction metadata; join or pivot it with an approved attribute selection policy before using any curves in financial analysis. Do not treat raw HAZUS structural archetypes as roofing materials.

## Financial conventions

- A 30-year horizon means 30 annual periods (offset 0 through 29), plus terminal valuation at offset 30.
- Operating flows are currently assigned to offset `t` (beginning-of-period convention for the pilot); future CADENCE adapter must confirm cash-flow timing.
- Replacement at terminal boundary is excluded; terminal service value is measured at that boundary.
- Costs are supplied in **constant real dollars**; no nominal escalation is applied here.
- Real discount rate is explicit; NPC is sum of discounted costs net of terminal credit.
- `incremental_npv_real = baseline_npc_real - option_npc_real`.
- If no replacement occurs before horizon, terminal value uses **existing_roof_basis_real**, not the candidate replacement price.
- Disabled annual streams are represented as explicit zeros by the upstream contract; missing rows/values are errors.
- Existing-roof remaining value is **not** separately charged as an early-retirement penalty.

## Core API

```python
from cadence_lifecycle import project_fixed_eul_events, build_cashflows, compare_options
```

See `docs/architecture.md`, `docs/data_contracts.md`, `docs/assumptions_register.md`, and `docs/validation_plan.md`.

## Development boundaries

One climate trajectory, geometry-free simulation, versioned immutable reference data, source-aware canonical mappings, no insurance rules engine, no per-asset Python loops, and no modification of main CADENCE. CADENCE's burnout/voluntary-upgrade precedence remains unresolved and is not decided here.
