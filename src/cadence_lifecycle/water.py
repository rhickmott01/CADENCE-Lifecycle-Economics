"""Research-informed event-level roof entry and single-story water balance.

Hazard, fragility, rain and annualization remain upstream. See the methodology
for the distinction between published damage functions and reduced geometry.
"""
import polars as pl
from pydantic import BaseModel, ConfigDict, Field

from .contracts import ContractViolationError, require_columns, require_unique
from .disposal import require_finite

EVENT_KEYS = ["asset_id", "decision_year", "option_id", "offset", "event_id"]
COMPARTMENTS = ("ceiling", "partitions", "contents", "floor")


class WaterParameters(BaseModel):
    """Explicit capacities per wetted footprint; no calibrated defaults."""
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    parameter_set_id: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    covering_leakage_fraction: float = Field(ge=0, le=1)
    entry_efficiency: float = Field(ge=0, le=1)
    ceiling_capacity_l_per_m2: float = Field(gt=0)
    partitions_capacity_l_per_m2: float = Field(gt=0)
    contents_capacity_l_per_m2: float = Field(gt=0)
    floor_capacity_l_per_m2: float = Field(gt=0)


def interior_damage_ratio(wetness: pl.Expr) -> pl.Expr:
    """Abreu (2019), p42 eq2, with explicit physical [0,1] clipping."""
    x = wetness.clip(0, 1)
    return (x.pow(5) / 2 + 0.6785 * x).clip(0, 1)


def interior_event_losses(events: pl.DataFrame, parameters: WaterParameters) -> pl.DataFrame:
    """Roof-entry volume, four serial reservoirs and five interior loss components.

    Values apply only to the wetted footprint, excluding roof and contents.
    Rain is upstream accumulated effective incident roof rain in mm.
    Cover loss applies to intact deck remainder, avoiding overlapping openings.
    All capacities are per m² of wetted footprint, not per wall surface area.
    """
    values = ["ceiling_value_real", "partitions_value_real", "floor_value_real",
              "cabinets_value_real", "electrical_value_real"]
    fields = ["roof_area_m2", "wetted_area_m2", "effective_rain_mm",
              "deck_breach_fraction", "cover_loss_fraction", "base_dollar_year"] + values
    require_unique(events, EVENT_KEYS, "water events")
    require_columns(events, fields + ["source_version"], "water events")
    require_finite(events, fields + ["decision_year", "offset"], "water events")
    if events.is_empty() or events.filter(
        pl.any_horizontal(*[pl.col(c).is_null() for c in EVENT_KEYS])
        | pl.col("source_version").is_null() | (pl.col("source_version").str.strip_chars() == "")
        | (pl.col("roof_area_m2") <= 0) | (pl.col("wetted_area_m2") <= 0)
        | (pl.col("effective_rain_mm") < 0)
        | pl.any_horizontal(*[pl.col(c) < 0 for c in values])
        | ~pl.col("deck_breach_fraction").is_between(0, 1)
        | ~pl.col("cover_loss_fraction").is_between(0, 1)
        | ~pl.col("base_dollar_year").is_between(1900, 2200)
        | (pl.col("base_dollar_year") != pl.col("base_dollar_year").floor())
        | (pl.col("offset") < 0) | (pl.col("offset") != pl.col("offset").floor())
    ).height:
        raise ContractViolationError("Invalid water event identity, provenance, units or exposure")
    p = parameters
    result = events.with_columns(
        (pl.col("roof_area_m2") * (pl.col("deck_breach_fraction")
         + (1 - pl.col("deck_breach_fraction")) * pl.col("cover_loss_fraction")
         * p.covering_leakage_fraction)).alias("effective_opening_m2"),
    ).with_columns(
        (pl.col("effective_opening_m2") * pl.col("effective_rain_mm")
         * p.entry_efficiency).alias("water_entry_l"),
    )
    incoming = "water_entry_l"
    # Four component dimensions, vectorized over all asset/event rows.
    for component in COMPARTMENTS:
        capacity = getattr(p, f"{component}_capacity_l_per_m2")
        result = result.with_columns(
            (pl.col("wetted_area_m2") * capacity).alias(f"{component}_capacity_l")
        ).with_columns(
            pl.min_horizontal(incoming, f"{component}_capacity_l").alias(f"{component}_retained_l")
        ).with_columns(
            (pl.col(incoming) - pl.col(f"{component}_retained_l")).alias(f"{component}_overflow_l"),
            (pl.col(f"{component}_retained_l") / pl.col(f"{component}_capacity_l")).alias(f"{component}_wetness"),
        )
        incoming = f"{component}_overflow_l"
    result = result.with_columns(
        *[interior_damage_ratio(pl.col(f"{c}_wetness")).alias(f"{c}_damage_ratio")
          for c in ("ceiling", "partitions", "floor")],
        pl.col("floor_overflow_l").alias("ponded_water_l"),
    ).with_columns(
        (0.6 * pl.col("floor_damage_ratio") + 0.4 * pl.col("partitions_damage_ratio")).alias("cabinets_damage_ratio"),
        (0.4 * pl.col("ceiling_damage_ratio") + 0.6 * pl.col("partitions_damage_ratio")).alias("electrical_damage_ratio"),
    ).with_columns(
        pl.sum_horizontal(*[pl.col(f"{c}_value_real") * pl.col(f"{c}_damage_ratio")
                            for c in ("ceiling", "partitions", "floor", "cabinets", "electrical")]).alias("interior_loss_real"),
        pl.lit(p.parameter_set_id).alias("water_parameter_set_id"),
        pl.lit(p.source_reference).alias("water_method_reference"),
        pl.lit("provisional_single_story_v1; uncalibrated").alias("model_status"),
    )
    require_finite(result, ["water_entry_l", "ponded_water_l", "interior_loss_real"], "water result")
    return result
