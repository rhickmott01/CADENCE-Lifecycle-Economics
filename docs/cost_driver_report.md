# Component-level NPV report

## Run the illustrative report

From `CADENCE-Lifecycle-Economics`, with the existing development environment:

```bash
.venv/bin/python -m pip install -e '.[dev,report]'
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/run_cost_driver_analysis.py
```

The command reads sibling CADENCE source and shared references, and writes only under this repository. `--shared-root` selects the shared `reference_data` directory; `--cadence-root` selects the upstream source checkout. `--output-root` must resolve inside this repository. `scripts/run_disposal_npv_pilot.py` is now a compatibility entry point to the same generated-event report. Historical pilot outputs are preserved.

Each run is published under `outputs/cost_driver_analysis/schema_version=v0.1/run_id=.../`. Publication is staged, and existing runs are never overwritten. For an independent reproduction use another output root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/run_cost_driver_analysis.py \
  --output-root outputs/cost_driver_reproduction
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider
```

## Outputs and accounting

| Artifact | Purpose |
| --- | --- |
| `npv_contributions.csv` / `.parquet` | One row per asset, decision year, option, and component; baseline PV, option PV, incremental contribution, enabled status, source, source year, valuation method, dollar base, and timing |
| `npv_contributions.svg` / `.png` | Standalone chart of enabled component contributions and net NPV; positive favors the upgrade |
| `option_results.csv` / `.parquet` | Existing NPC/NPV totals, component sum, and reconciliation error |
| `disposal_events.csv` / `.parquet` | Generated event dates, installed/removed materials, mass, fee, and geographic fallback level |
| Other Parquet tables | Options, annual costs/cash flows, metadata, exact-source mass/service-life references, and selected housing reference |
| `run_metadata.json`, `provenance.json` | Configuration, package versions, input/code hashes, local HEAD context, artifact hashes, and reproduction command |

`component contribution = baseline component PV − option component PV`.
Components sum to the existing `compare_options()` incremental NPV. The reporter uses discount factors emitted by `build_cashflows()` rather than reconstructing them from total costs. Salvage and terminal service value enter as negative costs. A 30-year horizon retains annual offsets 0–29 and terminal valuation at 30; terminal-boundary replacement is excluded. Annual/terminal row types and full annual support are checked explicitly.

`build_component_report(cashflows, metadata, base_dollar_year)` requires complete finite cash flows and exactly one metadata row per asset/decision/option/component. Metadata fields are `enabled` (boolean), `source`, `source_year` (nullable), and `valuation_method`. Disabled streams must have explicit zero values; enabled missing values fail. Report source metadata is caller supplied and must identify the valuation policy honestly.

## Reuse boundary and material identity

`build_disposal_events()` calls the existing fixed-EUL scheduler. The first event removes `existing_material_id`; repeat events remove the installed option material. `attach_disposal()` only populates a previously zero disposal stream and rejects events outside annual support, missing prices, and possible duplicate charging.

The optional `upstream.py` bridge executes unmodified CADENCE `contracts.py`, `materials.py`, and `externalities.py` in a fresh Python process with bytecode writes disabled. It bypasses eager upstream package initializers to avoid importing unrelated geospatial/reporting pipelines. CADENCE's `_attach_disposal_cost()` supplies the existing state → EREF region → national fallback and short-ton pricing. The lifecycle package does not copy this pricing function or its state crosswalk. The bridge uses a private API; upstream source hashes are recorded and compatibility must be revalidated after upstream changes.

`load_material_mass()` delegates official-class consolidation to CADENCE's existing approved mapper and preserves its contributor fields. Its mapping CSV inputs are absent from this local workspace, so official-class lookup is blocked until they are supplied. No replacement map is invented. The pilot uses exact source identities `Architectural Asphalt Shingles` and `Metal Roofing`, preserving subtype identity without claiming official-class consolidation. Mass inputs are checked for positive finite values and square/square-foot consistency.

## Interpretation limits

- Installation costs ($12,000 asphalt; $25,000 metal), the existing-roof basis, and EUL/RUL overrides are illustrative pilot assumptions. They are not observed prices or consolidated physical service-life estimates. Installation remains one combined component; no unsupported material/labor split is introduced.
- North Carolina's EREF 2024 fee is $39.71 per short ton. Following CADENCE's `fixed_2026_real_proxy` convention, the source rate is held constant without an inflation conversion. Source year and financial base year remain separate in the report.
- Durham County FIPS `37063` has a selected HUD-derived 2025 two-bedroom rate of $62.40/day. Housing selection filters county/year/bedroom and accepts repeated identical rates only; conflicting rates fail. This reference is exported, but downtime costs remain disabled without supported annual expected days.
- Maintenance, repair/building loss, contents, downtime, debris, and salvage are explicitly disabled in this pilot. Casualty attribution is outside the decision total. The result therefore explains installation, routine disposal, and terminal service value; it is not a full climate-benefit valuation or a production upgrade recommendation.
- Hazard integration, repair-cost basis, age handling, and terminal-policy differences with CADENCE remain open. Disposal is routine roof removal, not an additional charge for already monetized hazard debris or installation cleanup.

Reproducibility is tested byte for byte for all published artifacts within the same runtime and source/reference versions. Manifests record the versions needed to reproduce the run; identical chart bytes across different Matplotlib/font/platform versions are not claimed. The run ID includes executable working-source hashes, not just a potentially dirty git HEAD. No research extraction pipeline or source dataset is modified.

The next modeling priorities are property damage beyond the roof, contents damage, and loss of use; see the [integration roadmap](PROJECT_CONTEXT.md#prioritized-integration-roadmap). The [casualty attribution specification](casualty_research_plan.md) is retained as deferred background.
