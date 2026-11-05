# Data contracts (draft v0.1)

## Options: one row per (asset_id, decision_year, option_id)

Required: `asset_id` string; `decision_year` int; `option_id` string; `material_id` canonical string; `initial_rul_years` nonnegative integer; `new_eul_years` positive integer; `replacement_cost_real` nonnegative float; `roof_area_sqft` positive float; `existing_roof_basis_real` nonnegative float; `existing_eul_years` positive integer. Include a `baseline` option for each asset/year.

## Annual costs: one row per (asset_id, decision_year, option_id, offset)

`offset` in `[0,horizon)`. Explicit real-dollar fields: `maintenance_real`, `building_loss_real`, `contents_loss_real`, `downtime_real`, `debris_brick_wood_real`, `debris_concrete_steel_real`, `disposal_real`, `salvage_credit_real`. All rows must be present. No missing-to-zero inference.

## Consequence curves

One row per `(asset_id,year,option_id,damage_type,wind_speed_mph)`; `response_value` is ratio for building/content, days for loss_of_use, lb/ft2 for both debris types. HAZUS age partitions are limited to 1..30. Caller must provide approved source-aware mapping, exact archetype/terrain and wind-gust units.

## Hazard probability masses

One row per `(asset_id,year,wind_speed_mph)`, nonnegative `probability_mass` summing to 1 within 1e-7. These masses are an **input from a verified AEL methodology**, not derived from return periods by this package.

## Exposure

One row per `(asset_id,year,option_id)` with `building_value_real`, `contents_value_real`, `daily_relocation_real`, `debris_area_sqft`, `debris_cleanup_per_ton_real`. The exposed area for HAZUS debris must be approved separately from roof area. All values nonnegative.

## Published outputs

`lifecycle_annual_cashflows` grain `(asset_id,decision_year,option_id,offset)`; includes terminal credit at offset 30. `lifecycle_option_results` grain `(asset_id,decision_year,option_id)`; contains NPC and incremental NPV. `lifecycle_replacement_events` grain `(asset_id,decision_year,option_id,event_year)`; event data is hypothetical.

Cash flows additionally expose `cashflow_type` (`annual` or `terminal`), `discount_factor`, and positive `terminal_credit_real` (zero on annual rows). Total costs subtract this credit. The reporter requires complete offsets from zero through a common terminal boundary. Component metadata, contribution outputs, disposal event inputs, and provenance are specified in [cost_driver_report.md](cost_driver_report.md).

## Upstream loss-of-use inputs

Consume a versioned annual displacement-days export or already-valued annual costs at `(asset_id,decision_year,option_id,offset)` grain. Keep hazard, climate, state and HAZUS annualization calculations in their owning repositories. Source/method IDs, validation status, annual timing, units and dollar-year provenance are required. See [loss_of_use_integration.md](loss_of_use_integration.md) for fields, validation rules and the optional housing valuation adapter.

## Source-value mappings

Source label, normalized label, source dataset ID, mapping version, relationship type, canonical material ID, approved proxy ID and confidence must be preserved upstream. Unknown, ambiguous or unapproved values cannot enter simulation.

## Full lifecycle exchange v1

The proposed [lifecycle exchange v1](lifecycle_exchange_v1.md) preserves upstream
physical `scenario_id` alongside financial `option_id` and a separate sensitivity
`assumption_set_id`. It adds an optional `interior_loss_real` stream to the existing
engine without changing legacy callers' schemas. Production callers supply their
replacement events and terminal values rather than using the fixed-EUL pilot.
All complete annual costs, component sources/statuses, base years and stream
boundaries are explicit. Parquet schemas, DuckDB joins and NPV/component
reconciliation are checked before immutable publication.
