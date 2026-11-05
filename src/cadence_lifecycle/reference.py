"""Read-only selection of published references; no extraction pipeline."""
from pathlib import Path
import polars as pl
from .contracts import ContractViolationError, require_columns
from .disposal import require_finite


def select_housing_rate(path: Path, county_fips: str, source_year: int,
                        bedroom: str = "Two-Bedroom") -> pl.DataFrame:
    """Accept identical repeated rates; reject conflicting county/year/bedroom rates."""
    if len(county_fips) != 5 or not county_fips.isdigit():
        raise ContractViolationError("county_fips must be a five-character digit string")
    frame = pl.read_csv(path, schema_overrides={"county_fips": pl.String})
    require_columns(frame, ["year", "county_fips", "primary_bedroom", "relocation_cost_per_day"], "housing")
    bedroom_columns = {
        "Efficiency": "daily_efficiency", "One-Bedroom": "daily_one_bedroom",
        "Two-Bedroom": "daily_two_bedroom", "Three-Bedroom": "daily_three_bedroom",
        "Four-Bedroom": "daily_four_bedroom",
    }
    if bedroom not in bedroom_columns:
        raise ContractViolationError("Unsupported housing bedroom category")
    selected = frame.filter(
        (pl.col("county_fips").str.zfill(5) == county_fips)
        & (pl.col("year") == source_year)
    )
    source_column = bedroom_columns[bedroom]
    if source_column in frame.columns:
        # The published file contains all bedroom tiers, even though its
        # relocation_cost_per_day convenience column uses one primary tier.
        selected = selected.with_columns(pl.col(source_column).alias("relocation_cost_per_day"))
    else:
        selected = selected.filter(pl.col("primary_bedroom") == bedroom)
    if selected.is_empty():
        raise ContractViolationError("No housing rate for requested county/year/bedroom")
    require_finite(selected, ["relocation_cost_per_day"], "housing rates")
    if selected["relocation_cost_per_day"].n_unique() != 1:
        raise ContractViolationError("Ambiguous county housing rates; explicit geographic policy required")
    if selected["relocation_cost_per_day"][0] < 0:
        raise ContractViolationError("Negative housing rate")
    return pl.DataFrame({
        "county_fips": [county_fips], "source_year": [source_year], "bedroom": [bedroom],
        "relocation_cost_per_day": [selected["relocation_cost_per_day"][0]],
        "observation_count": [selected.height],
        "selection_method": ["county_year_bedroom_unique_rate"],
    })
