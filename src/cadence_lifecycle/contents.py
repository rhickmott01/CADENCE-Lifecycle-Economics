"""Separate contents valuation from the shared component water balance."""
import polars as pl

from .contracts import ContractViolationError, require_columns, require_unique
from .disposal import require_finite
from .water import EVENT_KEYS


def contents_event_losses(water: pl.DataFrame) -> pl.DataFrame:
    """Abreu (2019), p42 eq3; radians, sin(x)**1.5/2 + x**20.

    Explicitly cap damage at 1 (the published expression exceeds 1 near x=1).
    Contents value is caller supplied for the exposed footprint in the same base
    dollar year. No contents/building valuation factor or inventory is invented.
    """
    require_unique(water, EVENT_KEYS, "contents events")
    require_columns(water, ["base_dollar_year", "water_parameter_set_id"], "water result")
    require_finite(water, ["contents_wetness", "contents_value_real"], "contents input")
    if water.filter(~pl.col("contents_wetness").is_between(0, 1)
                    | (pl.col("contents_value_real") < 0)).height:
        raise ContractViolationError("Invalid contents exposure or wetness")
    x = pl.col("contents_wetness")
    return water.with_columns(
        (x.sin().pow(1.5) / 2 + x.pow(20)).clip(0, 1).alias("contents_damage_ratio")
    ).with_columns(
        (pl.col("contents_value_real") * pl.col("contents_damage_ratio")).alias("contents_loss_real"),
        pl.lit("Abreu_2019_p42_eq3; bounded_0_1").alias("contents_method_id"),
    )
