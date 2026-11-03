"""Join generated replacement events to removed-roof mass and upstream pricing."""

from pathlib import Path

import polars as pl

from .cashflows import KEYS
from .contracts import ContractViolationError, require_columns, require_unique
from .replacement import project_fixed_eul_events
from .upstream import price_disposal


def require_finite(frame: pl.DataFrame, columns: list[str], label: str) -> None:
    require_columns(frame, columns, label)
    if frame.select(pl.any_horizontal(
        *[pl.col(c).is_null() | ~pl.col(c).is_finite() for c in columns]
    )).to_series().any():
        raise ContractViolationError(f"{label}: missing or nonfinite numeric values")


def read_source_mass(path: Path) -> pl.DataFrame:
    """Exact source-subtype identities only; never infer an official-class map."""
    mass = pl.read_csv(path)
    require_unique(mass, ["asset_class"], "source mass")
    require_finite(mass, ["weight_per_square_lbs", "weight_per_sqft_lbs"], "source mass")
    if mass.filter(
        (pl.col("weight_per_sqft_lbs") <= 0)
        | ((pl.col("weight_per_square_lbs") / 100 - pl.col("weight_per_sqft_lbs")).abs() > 1e-9)
    ).height:
        raise ContractViolationError("Invalid mass or inconsistent roofing-square units")
    return mass.rename({"asset_class": "material_id"}).with_columns(
        pl.lit("exact_source_subtype").alias("mass_mapping_method")
    )


def build_disposal_events(options: pl.DataFrame, mass: pl.DataFrame,
                          fees_path: Path, cadence_root: Path,
                          horizon_years: int = 30) -> pl.DataFrame:
    """First event removes the existing roof; later events remove the option roof.

    Options add existing_material_id and state_code to the lifecycle contract.
    Mass is either exact source-subtype data or a caller-supplied approved CADENCE
    lookup renamed to material_id. Pricing delegates to unmodified CADENCE code.
    """
    require_columns(options, KEYS + ["existing_material_id", "state_code"], "options")
    require_unique(mass, ["material_id"], "mass")
    require_columns(mass, ["mass_mapping_method"], "mass")
    require_finite(options, ["roof_area_sqft", "initial_rul_years", "new_eul_years"], "options")
    require_finite(mass, ["weight_per_sqft_lbs"], "mass")
    if mass.filter(pl.col("weight_per_sqft_lbs") <= 0).height:
        raise ContractViolationError("Roof mass must be positive")
    if mass.filter(pl.col("mass_mapping_method").is_null()
                   | ~pl.col("mass_mapping_method").is_in(["exact_source_subtype", "approved_cadence_lookup"])).height:
        raise ContractViolationError("Explicit exact-source or approved CADENCE mass identity required")
    fees = pl.read_csv(fees_path)
    require_unique(fees, ["Region/State"], "tipping fees")
    require_finite(fees, ["Average tipping Fee"], "tipping fees")
    if fees.filter(pl.col("Average tipping Fee") < 0).height:
        raise ContractViolationError("Negative tipping fee")
    for column in ("material_id", "existing_material_id", "state_code"):
        if options.filter(pl.col(column).is_null() | (pl.col(column).str.len_chars() == 0)).height:
            raise ContractViolationError(f"Missing {column}")
    if options.filter(
        (pl.col("initial_rul_years") != pl.col("initial_rul_years").floor())
        | (pl.col("new_eul_years") != pl.col("new_eul_years").floor())
    ).height:
        raise ContractViolationError("Fixed-EUL event timing requires integer years")
    events = project_fixed_eul_events(options, horizon_years).join(
        options.select(KEYS + ["initial_rul_years", "existing_material_id", "roof_area_sqft", "state_code"]),
        on=KEYS, validate="m:1",
    ).with_columns(
        pl.when(pl.col("offset") == pl.col("initial_rul_years"))
        .then(pl.col("existing_material_id")).otherwise(pl.col("material_id"))
        .alias("removed_material_id")
    ).join(
        mass.rename({"material_id": "removed_material_id"}),
        on="removed_material_id", how="left", validate="m:1",
    )
    require_finite(events, ["weight_per_sqft_lbs"], "removed-material lookup")
    events = events.with_columns(
        (pl.col("roof_area_sqft") * pl.col("weight_per_sqft_lbs")).alias("removed_roof_mass_lbs")
    )
    columns = KEYS + ["offset", "event_year", "event_type", "material_id", "removed_material_id",
                       "roof_area_sqft", "state_code", "weight_per_sqft_lbs", "removed_roof_mass_lbs",
                       "mass_mapping_method"]
    columns += [c for c in ("source_reference", "typical_service_life_years", "weight_per_square_lbs",
                            "contributing_canonical_ids", "shared_mass_value_applied", "official_material_id")
                if c in events.columns]
    if events.is_empty():
        return events.select(columns).with_columns(
            pl.lit(None, dtype=pl.Float64).alias("disposal_fee_usd_per_short_ton"),
            pl.lit(None, dtype=pl.String).alias("disposal_geography_level"),
            pl.lit(None, dtype=pl.Float64).alias("disposal_real"),
            pl.lit(None, dtype=pl.String).alias("state_name"),
            pl.lit(None, dtype=pl.String).alias("eref_region"),
        )
    priced = price_disposal(cadence_root, events.select(columns), fees_path)
    require_finite(priced, ["disposal_cost_usd", "disposal_fee_usd_per_short_ton"], "disposal pricing")
    if priced.filter(pl.col("disposal_cost_usd") < 0).height:
        raise ContractViolationError("Negative disposal price")
    return priced.select(columns + ["disposal_fee_usd_per_short_ton", "disposal_geography_level",
                                    "state_name", "eref_region", "disposal_cost_usd"]).rename(
        {"disposal_cost_usd": "disposal_real"}
    ).sort(KEYS + ["offset"])


def attach_disposal(annual: pl.DataFrame, events: pl.DataFrame) -> pl.DataFrame:
    """Populate a previously zero disposal stream; refuse possible double charging."""
    keys = KEYS + ["offset"]
    require_unique(annual, keys, "annual costs")
    require_unique(events, keys, "disposal events")
    require_finite(annual, ["disposal_real"], "annual disposal")
    require_finite(events, ["disposal_real"], "event disposal")
    if annual.filter(pl.col("disposal_real") != 0).height:
        raise ContractViolationError("Disposal stream already populated; refusing double counting")
    if events.join(annual.select(keys), on=keys, how="anti").height:
        raise ContractViolationError("Disposal events lie outside annual cash-flow support")
    return annual.drop("disposal_real").join(
        events.select(keys + ["disposal_real"]), on=keys, how="left", validate="1:1"
    ).with_columns(pl.col("disposal_real").fill_null(0.0))
