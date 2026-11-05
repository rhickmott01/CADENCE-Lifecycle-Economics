# Loss-of-use inputs and repository boundary

## Ownership

Upstream CADENCE repositories own hazard preparation, climate trajectories, roof-state transitions, approved construction/material mappings, and HAZUS annualization. Lifecycle Economics consumes their validated annual outputs. It does not reproduce those pipelines or select new probability tails or climate extrapolation policies.

Use immutable, versioned Parquet exports with configurable input paths. Preserve authoritative IDs across repositories. A manifest should identify the schema version, producing repository/commit and dataset versions, input file hashes, units, climate trajectory, mapping/aggregation rules, hazard integration/tail policy, annual day-allocation convention, financial basis where applicable, and validation/completeness status. A Box path provides storage access; it does not establish scientific approval or replace the manifest.

All source repositories and Box datasets remain read-only. Derived costs, reports, and run manifests are written only inside Lifecycle Economics. No need to copy raw wind grids or the full HAZUS dataset into this repository.

## Preferred annual interfaces

| Input | Grain and required values | Treatment here |
| --- | --- | --- |
| Validated annual displacement | `asset_id`, `decision_year`, `option_id`, `offset`, `expected_loss_of_use_days`, `hazard_method_id`, `curve_mapping_id`, `source_version`, `validation_status`, `day_allocation_method` | Optional housing valuation through `build_loss_of_use_costs()` |
| Already-valued annual housing costs | `asset_id`, `decision_year`, `option_id`, `offset`, `downtime_real`, `base_dollar_year`, `source_version`, `validation_status`, `discount_status`, `cost_scope` | Direct attachment with `attach_loss_of_use()`; no second conversion or monetization |
| Housing asset attributes, if valuation is performed here | One row per `asset_id`: five-character `county_fips`, `bedroom` | Deterministic selection from existing shared references |
| Housing dollar conversion, if valuation is performed here | `HousingDollarBasis`: source/base years and periods, explicit positive factor, method ID, source reference | Apply the documented factor once, then hold rates constant in real dollars |

Choose one annual interface per run. `option_id` must distinguish baseline and alternatives; an official material class alone cannot distinguish existing and newly installed roofs of the same material at different ages. Upstream scenario IDs should be mapped explicitly to these option IDs, preserving the original IDs in the provenance ledger. A missing annual row or unapproved input is an error, not zero. `validation_status` must be `approved` with auditable method/source IDs; the consumer does not infer approval from a filename.

Annual costs must be undiscounted (`discount_status=undiscounted`) and use `cost_scope=storm_temporary_housing_before_insurance; constant_real`. Lifecycle applies its existing discount factors once. Values already discounted or net of insurance are rejected under this initial contract. If an annual-days export also provides `year`, it must equal `decision_year + offset`; the adapter rejects disagreements. Already-valued cost columns must not be passed through the days-to-cost path.

The annual-days interface means expected days that the household is away **within that financial year**. The producing calculation must account for long events and overlapping periods before export; raw event recovery durations are not annual expected days. Inputs exceeding the calendar year's day count are rejected rather than clipped. Leap years are retained. If upstream instead values an event's entire future accommodation stream at occurrence, that is a different timing contract and requires an explicitly reviewed adapter, not relabeling as within-year days.

If upstream exports costs, provide component metadata with the same `downtime` component name used by the report, plus source, source year, enabled status and valuation method. If this repository performs housing valuation, `loss_of_use_metadata()` produces that component metadata while the annual cost ledger retains method and conversion details. Replace the disabled `downtime` metadata rows with these enabled rows before calling `build_component_report()`.

## Valuation and NPV

Confirmed scope is one temporary housing unit per household/asset, storm-related displacement, before insurance reimbursements. County and bedroom tier are configurable; the demonstration uses Durham County `37063` and a two-bedroom unit. The source rate is $62.40/day in the shared 2025 HUD-derived dataset. Its price conversion to the 2026 report base must be documented before numerical use; no real conversion factor has been selected yet. No moving, storage, meal, planned roof-work or insurance assumptions are introduced.

`build_loss_of_use_costs()` calls the existing `monetize_consequences()` function using only the active loss-of-use exposure. Unused building/content/debris price fields are not fabricated. Housing lookup uses the requested published bedroom-tier rate; duplicated county observations must agree on that rate. The adapter loops over unique reference geographies/housing sizes, not individual assets.

`attach_loss_of_use(..., base_dollar_year=2026)` requires complete annual support, approved source provenance, and a matching dollar base. It rejects a previously populated downtime stream to prevent duplicate charges. Existing `build_cashflows()`, `compare_options()` and `build_component_report()` retain responsibility for discounting, baseline subtraction, and reconciliation.

The incremental component remains `baseline housing PV - option housing PV`. Identical annual housing costs give zero loss-of-use benefit. Keep the current 30-year horizon, 3% real discount rate, and offset-t convention unless a later timing change is approved. Existing installation/disposal/terminal credits remain separately accounted for.

## Box partition inspection

The supplied `iecc2021/1A/age_01` partition is accessible. The read-only inspector checks only the three selected files, counts and fingerprints the source, and verifies loss-of-use curve/point support. It does not calculate annual displacement or approve proxies:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/inspect_loss_of_use.py \
  /path/to/iecc2021/1A/age_01 \
  --output outputs/loss_of_use_inspection/1A_age_01.json
```

Inspection output is write-once. This sample is climate zone 1A, age 1; it is not evidence that these are the correct Durham inputs. The schema has no explicit response-unit field, and residential occupancy is not supplied on these curve rows. Source interpretation and applicability must be established upstream rather than assumed from the `loss_of_use` label. CADENCE's ratio-bounded damage integrator cannot be applied directly to duration responses.

The documented source is FEMA Hazus 6.1, workbook `HazusWindDamFunctions_Hazus61.xlsx`, table `huDamLossFun`, transformed with `recursive-horizontal-v1`. The original workbook/dictionary and the transformation methodology still need to support the displacement interpretation and the scenario mappings. This repository's structural audit is not a scientific validation of those assumptions.

No observed or HAZUS-derived loss-of-use NPV is published until the validated annual export and documented housing price basis are supplied. Synthetic fixtures test the adapter and NPV reconciliation only; they are not research estimates.
