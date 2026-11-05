# Lifecycle analytical exchange v1

This is a proposed, versioned analytical contract informed by the verified
[Portfolio Mapping audit](portfolio_compatibility.md). It does not replace a
production CADENCE schema or execute adoption/state decisions.

## Reproduce

From the repository root, using its environment:

```sh
./.venv/bin/python -B scripts/run_full_lifecycle.py
./.venv/bin/python -B scripts/run_full_lifecycle.py --sensitivity --samples 8 --seed 20261104 --output-root outputs/full_lifecycle_final
./.venv/bin/python -m pytest -q
```

The default demonstrates all five requested pathways with an existing asphalt
baseline, immediate asphalt replacement and metal upgrade. Low/central/high
assumption sets are separate immutable runs. These are explicitly illustrative;
synthetic wind/roof/rain/downtime assumptions are not validated HAZUS exports.
Use `--horizon` and `--discount-rate` for alternative financial settings. Existing
run directories are never overwritten: choose a fresh `--output-root` for an
identical rerun. Changed input/code/config identities create a distinct run ID.

The only runtime source reuse is the opt-in existing CADENCE disposal subprocess
bridge. It loads unmodified upstream pricing code with bytecode disabled. All
generated artifacts stay inside Lifecycle Economics; sibling repositories and
datasets remain read-only. Installed prices/EUL/maintenance, inventory values,
damage and downtime in the demo are explicit fixtures. Landfill mass, tipping fee
and the unconverted HUD housing rate are read from actual source CSVs.

## Supplied inputs and production state

```sh
./.venv/bin/python -B scripts/run_full_lifecycle.py --input-dir /path/to/prepared_inputs --output-root outputs/supplied_run
```

The directory supplies `options.parquet`, `annual_costs.parquet`,
`component_metadata.parquet`, and `config.json`. For
`event_policy=upstream_events_and_terminal`, also supply
`replacement_events.parquet` and `terminal_values.parquet`.
`AnalysisConfig` in `analysis.py` is the strict JSON schema: unknown fields fail.

An example configuration is:

```json
{
  "horizon_years": 25,
  "real_discount_rate": 0.02,
  "base_dollar_year": 2026,
  "baseline_option_id": "BASELINE_CURRENT",
  "assumption_set_id": "upstream_reference_case",
  "data_status": "upstream_validated",
  "source_version": "caller-supplied-run-and-code-identity",
  "roof_loss_scope": "roof_exterior_only",
  "water_loss_scope": "separate_nonoverlapping",
  "contents_loss_scope": "separate_water_only",
  "replacement_cost_scope": "installed_excludes_disposal_and_damage",
  "loss_of_use_scope": "temporary_housing_before_insurance",
  "event_policy": "upstream_events_and_terminal",
  "overlap_method_id": "caller-supplied-reviewed-channel-extraction-method"
}
```

`data_status=upstream_validated` requires `validation_status=approved` on options,
annual inputs, replacement events and terminal values. This is a caller/source
attestation, not validation conferred by the adapter. The provisional water model
and synthetic fixtures must not be promoted to that status. Use `illustrative`
for uncalibrated scenarios. Annual hazard likelihoods, climate, physical roof
state, damage-to-rain relationships and expected displacement days stay upstream.

| Input | Required grain and fields |
| --- | --- |
| Options | `(asset_id, decision_year, option_id)`; `scenario_id`, `base_dollar_year`, `source_version`; source IDs remain strings |
| Annual costs | Option key + integer `offset`; all existing `STREAMS` plus `interior_loss_real`; `base_dollar_year`, `source_version` |
| Metadata | Option key + `component`; Boolean `enabled`, `source`, nullable `source_year`, `valuation_method` |
| Upstream events | Option key + `offset`; `event_cost_real` (installed cost excluding disposal), `removed_material_id`, installed `material_id`, source version, dollar base; preserve event year/area when supplied |
| Upstream terminal values | One per option; `terminal_value_real`, source version, dollar base; explicit zero for no-terminal-credit policy |

Annual costs contain `maintenance_real`, `building_loss_real` (roof/exterior under
the stated scope), `interior_loss_real`, `contents_loss_real`, `downtime_real`,
`disposal_real`, `debris_brick_wood_real`, `debris_concrete_steel_real`,
`salvage_credit_real`. All are undiscounted nonnegative magnitudes. Credits receive
their negative sign in cash flows. Every option/year must be present. A disabled
stream has explicit zero **and disabled metadata**; an enabled missing value
fails rather than generating a misleading numeric total.

For the fixed-EUL **illustrative-only** policy, options additionally use the
existing replacement contract (`material_id`, RUL, new EUL, installed price, area,
existing roof basis and EUL). The production path accepts upstream events and
terminal values and never generates competing state transitions.

`cadence_exchange.adapt_cadence_analysis` translates verified
`annual_alternative_analysis` fields: `annual_repair_cost_usd`,
`installation_event_capex_usd`, `enabled_event_disposal_cost_usd`,
`expected_loss_of_use_usd`, scenario material and removed material. It preserves
`scenario_id`, sets `option_id=scenario_id`, and requires explicit supplemental
streams, a matching source dollar basis, and explicit no-terminal-credit policy.
An enabled carbon stream is rejected rather than dropped because this exchange
does not implement carbon. Incomplete upstream flags fail; a partial cumulative
NPV is never consumed as an annual cost. Approval fields must be added/preserved
by the reviewed upstream export before a validated run.

No official class is inferred from a source subtype. If an upstream asset/scenario
crosswalk is used, it must be explicit and versioned. The fixture's exact source
mass IDs are not approved HAZUS proxies. The raw-Hazus AEL/RUL stubs remain blocked
deliberately: input adaptation does not authorize a new physical simulation.

## Financial and overlap policies

Annual operating costs, installations and removals occur at offset `t`, discounted
by `(1+r)^-t`. There are `H` periods, offsets `0..H-1`, plus a terminal credit at
`H`. No replacement occurs at the terminal boundary. Existing-roof residual basis
is separate from new installed cost. Supplied terminal policies override the
pilot calculation; zero credit permits comparison with inspected CADENCE.

`NPC = sum(discounted signed costs)`;
`incremental NPV = baseline NPC - option NPC`;
`component contribution = baseline component PV - option component PV`.
Every report verifies component NPC and incremental NPV reconciliation with
absolute/relative tolerances `1e-8 + 1e-10*abs(total)`.

Do not add total HAZUS building losses to separate interior damage. The config
rejects that populated combination. Contents is a single replacement channel:
use separate water contents or the upstream total, never their sum. Installation
inputs exclude separate disposal/damage streams; no material/labor split is
invented. Disposal represents landfill tipping only. Tear-off labor, transport,
hazard debris cleanup, casualty, insurance and community risk are excluded unless
separately supported under a future contract. Maintenance and salvage require
explicit supplied values or disabled status.

## Outputs

Published under `schema_version=lifecycle_exchange_v1/run_id={24-char-hash}/`.
Run IDs include configuration, every table's input identity, source/code hashes,
and installed numerical-library versions. `run_id` is also a column in every
Parquet table. All logical financial tables retain `asset_id`, decision year,
`option_id`, upstream `scenario_id`, `assumption_set_id`, `data_status`, dollar base
and exchange version. Financial scenario IDs are not overwritten by sensitivity.

| Table | Grain / additional columns |
| --- | --- |
| `annual_lifecycle_cashflows` | Option key + offset + cost component; calendar year, annual signed real cost, discounted cost, type, source/year/method, enabled, completeness |
| `annual_cashflows` | Option key + offset; wide components, discount factor, signed total, discounted total; includes terminal row |
| `replacement_events` | Option key + event offset; installed price, removed/installed materials, event year; demo also mass, area and disposal |
| `annual_damage_components` | Option key + annual offset; year, roof/exterior, interior, contents, housing loss |
| `lifecycle_summary` | Option key; NPC, baseline NPC, incremental NPV, dense investment rank (lower NPC ranks first) |
| `npv_contributions` | Option key + component; baseline PV, option PV, contribution, source/status and totals |
| `component_metadata` | Full component status and source register |
| `terminal_values` | Option key; explicit eligible service value/policy |
| `options`, `annual_costs` | Source-aware inputs retained for joins and audit |
| `event_water_damage` (demo) | Conditional events, rain/openings, values, each retained reservoir and ponded volume, damage ratios and methods |
| `sensitivity_results` (optional) | Case + option; parameter/endpoint or joint sample ID, seed, method, NPC/NPV/rank |

Auxiliary demo tables preserve housing/reference years, mass/event costs, hazard
mass fixture, water parameters and financial/physical assumption values.
`schemas.json` records actual typed schemas and row counts. `run_metadata.json`
records config, source hashes and software versions. `artifact_checksums.json`
covers published tables, metadata, CSVs and plots. CSV summaries and SVG/PNG
component charts support review. Raw private source files are not copied into Git.

Before atomic publication the publisher validates required logical schemas,
uniqueness, finite values and string IDs; roundtrips every Parquet table with
Polars; reads every table with DuckDB; and tests its annual-to-option identity
join. Leading-zero county IDs survive as strings. The geometry-free analytical
tables can join to the upstream asset map by asset ID. A dashboard adapter is
still required: these files are not drop-in replacements for its current v0.4.0
summary and annual schema.

## Uncertainty

Low/central/high are joint **assumption sets**, not confidence bounds. Optional
one-at-a-time endpoint cases isolate all eleven exposed fixture controls. Seeded
Monte Carlo uses independent triangular distributions over these same explicit
endpoints/mode; dependence and probabilities are assumed, not estimated. The
results propagate conditional water losses through the existing supplied-mass
integration and financial engine. EUL changes generate replacement schedules
through the existing engine. Nonlinear reservoir thresholds can change rankings;
more water need not increase the *difference* between already saturated options.
Default central inputs and endpoint values are in `demo.SCENARIOS`, and all are
exported. These distributions should be replaced with calibrated upstream joint
rain/breach/exposure uncertainty before any production decision.

The read-only reconciliation test invokes the actual local CADENCE annual
economics function on identical synthetic scenario, event and annual cost inputs.
With matched offset timing, dollar base, discount rate and **zero terminal
credit**, its NPV matches this engine across all four upstream physical scenario
IDs. This is a financial-interface regression, not validation of hazard integration,
production roof-state transitions, mappings, or new water-loss predictions.
