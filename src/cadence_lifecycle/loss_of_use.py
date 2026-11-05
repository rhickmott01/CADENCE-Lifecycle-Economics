"""Monetize validated annual displacement inputs using existing consequence math.

This adapter does not infer annual days from raw curves, choose proxies, integrate
return periods, or select inflation data. Those source decisions stay explicit.
"""
from pathlib import Path

import polars as pl
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .cashflows import KEYS
from .consequences import monetize_consequences
from .contracts import ContractViolationError, require_columns, require_unique
from .disposal import require_finite
from .reference import select_housing_rate

HOUSING_SCOPE = "storm_temporary_housing_before_insurance; constant_real"


class HousingDollarBasis(BaseModel):
    """A supplied, documented source-to-base conversion; no implicit proxy."""
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False, str_strip_whitespace=True)
    source_year: int = Field(ge=1900, le=2200)
    base_year: int = Field(ge=1900, le=2200)
    factor: float = Field(gt=0)
    source_period: str = Field(min_length=1)
    base_period: str = Field(min_length=1)
    method_id: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)

    @model_validator(mode="after")
    def identical_periods(self):
        if self.source_period == self.base_period and self.factor != 1:
            raise ValueError("Identical price periods require a factor of one")
        return self


def build_loss_of_use_costs(expected_days: pl.DataFrame, assets: pl.DataFrame,
                           housing_path: Path, dollar_basis: HousingDollarBasis) -> pl.DataFrame:
    """Return annual housing costs with source and conversion provenance.

    Expected input grain is KEYS + offset. Required source fields are
    hazard_method_id, curve_mapping_id, source_version, validation_status, and
    day_allocation_method. Input days must already represent expected days away
    within that financial year, with long events allocated upstream. Raw event
    durations (including the observed 720-day curve values) are not annual inputs.
    Assets supply asset_id, county_fips and bedroom. One housing unit per asset.
    """
    keys = KEYS + ["offset"]
    source_fields = ["hazard_method_id", "curve_mapping_id", "source_version",
                     "validation_status", "day_allocation_method"]
    require_unique(expected_days, keys, "annual displacement")
    require_columns(expected_days, keys + ["expected_loss_of_use_days"] + source_fields, "annual displacement")
    require_columns(assets, ["asset_id", "county_fips", "bedroom"], "housing assets")
    require_unique(assets, ["asset_id"], "housing assets")
    if expected_days.is_empty():
        raise ContractViolationError("Annual displacement inputs are empty")
    if "downtime_real" in expected_days.columns:
        raise ContractViolationError("Already-valued costs must use direct attachment, not another monetization")
    require_finite(expected_days, ["decision_year", "offset", "expected_loss_of_use_days"], "annual displacement")
    if not expected_days.schema["decision_year"].is_integer() or not expected_days.schema["offset"].is_integer():
        raise ContractViolationError("Decision year and offset must be integer columns")
    if expected_days.filter(
        pl.any_horizontal(*[pl.col(c).is_null() | (pl.col(c).str.strip_chars().str.len_chars() == 0)
                            for c in source_fields + ["asset_id", "option_id"]])
        | (pl.col("validation_status") != "approved")
        | (pl.col("expected_loss_of_use_days") < 0)
        | (pl.col("offset") < 0) | (pl.col("offset") != pl.col("offset").floor())
    ).height:
        raise ContractViolationError("Approved, sourced annual displacement inputs are required")
    if "year" in expected_days.columns:
        require_finite(expected_days, ["year"], "upstream financial year")
        if expected_days.filter(pl.col("year") != pl.col("decision_year") + pl.col("offset")).height:
            raise ContractViolationError("Upstream year disagrees with decision year and offset")
    annual = expected_days.with_columns((pl.col("decision_year") + pl.col("offset")).alias("year"))
    if annual.filter((pl.col("year") < 1900) | (pl.col("year") > 2200)).height:
        raise ContractViolationError("Financial year outside supported range")
    # Calendar-year input support is explicit; never clip long source events.
    annual = annual.with_columns(
        ((pl.date(pl.col("year") + 1, 1, 1) - pl.date(pl.col("year"), 1, 1))
         .dt.total_days()).alias("days_in_year")
    )
    if annual.filter(pl.col("expected_loss_of_use_days") > pl.col("days_in_year")).height:
        raise ContractViolationError("Allocate event durations to financial years before monetization")
    joined = annual.join(assets.select("asset_id", "county_fips", "bedroom"), on="asset_id", how="left", validate="m:1")
    if joined.filter(pl.col("county_fips").is_null() | pl.col("bedroom").is_null()).height:
        raise ContractViolationError("Missing asset geography/housing size")
    # Loop over reference dimensions only, never individual assets or time rows.
    rates = pl.concat([
        select_housing_rate(housing_path, county, dollar_basis.source_year, bedroom)
        for county, bedroom in joined.select("county_fips", "bedroom").unique().sort("county_fips", "bedroom").iter_rows()
    ])
    joined = joined.join(rates, on=["county_fips", "bedroom"], how="left", validate="m:1").with_columns(
        (pl.col("relocation_cost_per_day") * dollar_basis.factor).alias("daily_relocation_real")
    )
    require_finite(joined, ["daily_relocation_real"], "converted housing rates")
    # Reuse the existing monetization function. Multiple decision years can share
    # an asset/year/option, so retain decision identity in an internal batch key.
    batched = joined.with_row_index("_input_row").with_columns(pl.col("_input_row").cast(pl.String).alias("_valuation_asset_id"))
    expected = batched.select(
        pl.col("_valuation_asset_id").alias("asset_id"), "year", "option_id",
        pl.lit("loss_of_use").alias("damage_type"),
        pl.col("expected_loss_of_use_days").alias("expected_response"),
    )
    exposure = batched.select(pl.col("_valuation_asset_id").alias("asset_id"), "year", "option_id", "daily_relocation_real")
    costs = monetize_consequences(expected, exposure).select(
        pl.col("asset_id").alias("_valuation_asset_id"), pl.col("cost_real").alias("downtime_real")
    )
    return batched.join(costs, on="_valuation_asset_id", validate="1:1").drop(
        "_input_row", "_valuation_asset_id"
    ).with_columns(
        pl.lit(dollar_basis.base_year).alias("base_dollar_year"),
        pl.lit(dollar_basis.factor).alias("source_to_base_factor"),
        pl.lit(dollar_basis.method_id).alias("conversion_method_id"),
        pl.lit(dollar_basis.source_reference).alias("conversion_source_reference"),
        pl.lit(dollar_basis.source_period).alias("source_price_period"),
        pl.lit(dollar_basis.base_period).alias("base_price_period"),
        pl.lit(HOUSING_SCOPE).alias("cost_scope"),
        pl.lit("undiscounted").alias("discount_status"),
    ).sort(keys)


def attach_loss_of_use(annual: pl.DataFrame, costs: pl.DataFrame, *,
                       base_dollar_year: int) -> pl.DataFrame:
    """Attach already-valued annual housing costs once; missing years are errors.

    Accepts either build_loss_of_use_costs output or upstream-valued costs with
    source_version, validation_status=approved, matching base_dollar_year,
    discount_status=undiscounted and the agreed temporary-housing cost_scope.
    """
    keys = KEYS + ["offset"]
    require_unique(annual, keys, "annual costs")
    require_unique(costs, keys, "loss-of-use costs")
    require_finite(annual, ["downtime_real"], "existing downtime stream")
    require_finite(costs, ["downtime_real"], "loss-of-use costs")
    require_columns(costs, ["base_dollar_year", "validation_status", "source_version",
                            "discount_status", "cost_scope"], "loss-of-use costs")
    if costs.filter(
        pl.col("base_dollar_year").is_null() | (pl.col("base_dollar_year") != base_dollar_year)
        | pl.col("validation_status").is_null() | (pl.col("validation_status") != "approved")
        | pl.col("source_version").is_null() | (pl.col("source_version").str.strip_chars().str.len_chars() == 0)
        | pl.col("discount_status").is_null() | (pl.col("discount_status") != "undiscounted")
        | pl.col("cost_scope").is_null() | (pl.col("cost_scope") != HOUSING_SCOPE)
        | (pl.col("downtime_real") < 0)
    ).height:
        raise ContractViolationError("Approved cost provenance and a matching financial dollar base are required")
    if annual.filter(pl.col("downtime_real") != 0).height:
        raise ContractViolationError("Downtime stream already populated; refusing double counting")
    if (annual.join(costs.select(keys), on=keys, how="anti").height
            or costs.join(annual.select(keys), on=keys, how="anti").height):
        raise ContractViolationError("Loss-of-use costs must exactly cover annual cash-flow support")
    return annual.drop("downtime_real").join(costs.select(keys + ["downtime_real"]), on=keys, validate="1:1")


def loss_of_use_metadata(costs: pl.DataFrame) -> pl.DataFrame:
    """Component metadata for the optional housing monetization path."""
    require_columns(costs, KEYS + ["source_version", "source_year", "conversion_method_id"], "housing costs")
    return costs.group_by(KEYS).agg(
        pl.col("source_version").unique().sort().str.join("|").alias("source"),
        pl.col("source_year").first(),
        pl.col("conversion_method_id").unique().sort().str.join("|").alias("_conversion"),
    ).with_columns(
        pl.lit("downtime").alias("component"), pl.lit(True).alias("enabled"),
        pl.concat_str(pl.lit("validated_annual_days:"), pl.col("source"), pl.lit("; HUD housing reference")).alias("source"),
        pl.concat_str(pl.lit("housing_only; before_insurance; constant_real; dollar_conversion:"),
                      pl.col("_conversion")).alias("valuation_method"),
    ).drop("_conversion").sort(KEYS)
