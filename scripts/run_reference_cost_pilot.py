from pathlib import Path
import polars as pl

# Find shared data relative to the repository location.
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / "cadence_shared_data" / "reference_data"

DISPOSAL = DATA / "disposal" / "EREF_2024_Tipping_Fees_Parsed.csv"
HOUSING = DATA / "loss_of_use" / "temporary_housing_relocation_costs.csv"

# Initial geographic pilot
STATE_NAME = "North Carolina"
COUNTY_FIPS = "37063"  # Durham County

# --------------------------------------------------
# 1. Read existing source datasets
# --------------------------------------------------

fees = pl.read_csv(DISPOSAL)

housing = pl.read_csv(
    HOUSING,
    schema_overrides={"county_fips": pl.String}
)

# --------------------------------------------------
# 2. Resolve state disposal rate
# --------------------------------------------------

state_fees = fees.filter(
    pl.col("Region/State") == STATE_NAME
)

if state_fees.height != 1:
    raise ValueError(
        f"Expected one disposal rate for {STATE_NAME}"
    )

disposal_rate = float(
    state_fees["Average tipping Fee"][0]
)

# --------------------------------------------------
# 3. Resolve county relocation rate
# --------------------------------------------------

county = housing.filter(
    pl.col("county_fips").str.zfill(5) == COUNTY_FIPS
)

if county.is_empty():
    raise ValueError("County not found in HUD data")

# Reject ambiguous county-level rates.
# Main CADENCE currently uses .unique("county_fips"),
# which can hide different rates within a county.
unique_rates = county.select(
    pl.col("relocation_cost_per_day")
      .drop_nulls()
      .n_unique()
).item()

if unique_rates != 1:
    raise ValueError(
        "Multiple different relocation rates exist "
        "for this county. A geographic selection "
        "rule is required."
    )

housing_rate = float(
    county["relocation_cost_per_day"][0]
)

# --------------------------------------------------
# 4. Show normalized economic contributions
# --------------------------------------------------

# These unit-based examples are NOT modeled damage
# or replacement events.
result = pl.DataFrame({
    "cost_component": [
        "Disposal",
        "Loss of use"
    ],
    "geography": [
        STATE_NAME,
        COUNTY_FIPS
    ],
    "rate": [
        disposal_rate,
        housing_rate
    ],
    "unit": [
        "USD per short ton",
        "USD per displacement day"
    ],
    "source": [
        "EREF 2024",
        "HUD-derived 2025"
    ]
})

print("\n=== CADENCE SOURCE COST PILOT ===")
print(result)

# --------------------------------------------------
# 5. Export a reproducible input table
# --------------------------------------------------

output = ROOT / "outputs" / "reference_cost_pilot"
output.mkdir(parents=True, exist_ok=True)

result.write_csv(
    output / "reference_cost_rates.csv"
)

print("\nSaved to:", output.resolve())
