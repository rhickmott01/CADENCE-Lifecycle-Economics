
from pathlib import Path

import polars as pl

from cadence_lifecycle.cashflows import (
    STREAMS,
    build_cashflows,
    compare_options,
)
from cadence_lifecycle.replacement import project_fixed_eul_events

# ---------------------------------------------------
# 1. Simulation assumptions
# ---------------------------------------------------

START_YEAR = 2026
HORIZON = 30
DISCOUNT_RATE = 0.03

# All prices are illustrative constant 2026 dollars.
options = pl.DataFrame({
    "asset_id": ["house_001"] * 3,
    "decision_year": [START_YEAR] * 3,
    "option_id": [
        "baseline",
        "replace_asphalt_now",
        "upgrade_metal_now",
    ],
    "material_id": ["asphalt", "asphalt", "metal"],
    "initial_rul_years": [8, 0, 0],
    "new_eul_years": [20, 20, 40],
    "replacement_cost_real": [12000.0, 12000.0, 25000.0],
    "roof_area_sqft": [2000.0] * 3,
    "existing_roof_basis_real": [12000.0] * 3,
    "existing_eul_years": [20] * 3,
})

# ---------------------------------------------------
# 2. Build annual cost inputs
# ---------------------------------------------------

annual = options.select(
    "asset_id", "decision_year", "option_id"
).join(
    pl.DataFrame({"offset": range(HORIZON)}),
    how="cross",
)

# Disable optional cost streams for this first pilot.
for stream in STREAMS:
    annual = annual.with_columns(
        pl.lit(0.0).alias(stream)
    )

# ---------------------------------------------------
# 3. Calculate replacement schedules
# ---------------------------------------------------

events = project_fixed_eul_events(options, HORIZON)

print("\n=== REPLACEMENT SCHEDULE ===")
print(events.select(
    "option_id", "event_year", "event_cost_real"
))

# ---------------------------------------------------
# 4. Calculate annual lifecycle cash flows
# ---------------------------------------------------

cashflows = build_cashflows(
    options,
    annual,
    horizon_years=HORIZON,
    real_discount_rate=DISCOUNT_RATE,
)

# ---------------------------------------------------
# 5. Compare alternatives against baseline
# ---------------------------------------------------

results = compare_options(
    cashflows,
    baseline_option_id="baseline",
)

print("\n=== LIFECYCLE ECONOMIC RESULTS ===")
print(
    results.select(
        "option_id",
        "npc_real",
        "incremental_npv_real",
    ).sort("npc_real")
)

# ---------------------------------------------------
# 6. Export results for Excel / visualization
# ---------------------------------------------------

output = Path("outputs/pilot")
output.mkdir(parents=True, exist_ok=True)

events.write_csv(output / "replacement_schedule.csv")
cashflows.write_csv(output / "annual_cashflows.csv")
results.write_csv(output / "lifecycle_results.csv")

print("\nResults saved to:", output.resolve())
