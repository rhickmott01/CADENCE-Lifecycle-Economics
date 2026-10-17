"""Consequence units and integration; hazard probability convention is explicit."""
import polars as pl
from .contracts import ContractViolationError, require_columns, require_unique
MEASURES={"building_loss":"ratio","content_loss":"ratio","loss_of_use":"days","debris_brick_wood":"lb/ft2","debris_concrete_steel":"lb/ft2"}

def integrate_discrete_hazard(curve_responses:pl.DataFrame, hazard_weights:pl.DataFrame)->pl.DataFrame:
    """Integrate PRE-APPROVED discrete wind probability masses (not return periods).

    Caller must generate masses with the exact CADENCE AEL convention. No
    automatic interpolation, tail handling or conversion from return periods.
    Response input: asset_id, year, option_id, damage_type, wind_speed_mph, response_value.
    Weights: asset_id, year, wind_speed_mph, probability_mass; must sum to 1.
    """
    ck=["asset_id","year","option_id","damage_type","wind_speed_mph"]
    hk=["asset_id","year","wind_speed_mph"]
    require_columns(curve_responses,ck+["response_value"],"curve_responses")
    require_columns(hazard_weights,hk+["probability_mass"],"hazard_weights")
    require_unique(curve_responses,ck,"curve_responses")
    require_unique(hazard_weights,hk,"hazard_weights")
    if curve_responses.filter(~pl.col("damage_type").is_in(list(MEASURES))).height:
        raise ContractViolationError("unsupported damage type")
    if hazard_weights.filter((pl.col("probability_mass")<0)|pl.col("probability_mass").is_null()).height:
        raise ContractViolationError("invalid probability mass")
    totals=hazard_weights.group_by("asset_id","year").agg(pl.col("probability_mass").sum().alias("total"))
    if totals.filter((pl.col("total")-1).abs()>1e-7).height:
        raise ContractViolationError("hazard masses must sum to 1")
    joined=curve_responses.join(hazard_weights,on=hk,how="left",validate="m:1")
    if joined.filter(pl.col("probability_mass").is_null()|pl.col("response_value").is_null()).height:
        raise ContractViolationError("missing hazard support or curve response")
    if joined.filter((pl.col("response_value")<0)|((pl.col("damage_type").is_in(["building_loss","content_loss"]))&(pl.col("response_value")>1))).height:
        raise ContractViolationError("invalid response range")
    coverage=joined.group_by("asset_id","year","option_id","damage_type").agg(pl.col("probability_mass").sum().alias("coverage"))
    if coverage.filter((pl.col("coverage")-1).abs()>1e-7).height:
        raise ContractViolationError("curve does not cover complete hazard support")
    return joined.group_by("asset_id","year","option_id","damage_type").agg((pl.col("response_value")*pl.col("probability_mass")).sum().alias("expected_response"))

def monetize_consequences(expected:pl.DataFrame, exposure:pl.DataFrame)->pl.DataFrame:
    """Exposure fields: building_value_real, contents_value_real, daily_relocation_real,
    debris_area_sqft, debris_cleanup_per_ton_real. Debris measures are separately
    monetized; source attribution and double-counting approval remain upstream.
    """
    k=["asset_id","year","option_id"]
    require_columns(expected,k+["damage_type","expected_response"],"expected")
    require_columns(exposure,k+["building_value_real","contents_value_real","daily_relocation_real","debris_area_sqft","debris_cleanup_per_ton_real"],"exposure")
    require_unique(exposure,k,"exposure")
    joined=expected.join(exposure,on=k,how="left",validate="m:1")
    if joined.select(pl.any_horizontal(*[pl.col(c).is_null() for c in ["building_value_real","contents_value_real","daily_relocation_real","debris_area_sqft","debris_cleanup_per_ton_real"]])).to_series().any():
        raise ContractViolationError("missing exposure values")
    if joined.filter(pl.any_horizontal(*[pl.col(c)<0 for c in ["building_value_real","contents_value_real","daily_relocation_real","debris_area_sqft","debris_cleanup_per_ton_real"]])).height:
        raise ContractViolationError("negative exposure or cost")
    return (joined.with_columns(cost_real=pl.when(pl.col("damage_type")=="building_loss").then(pl.col("expected_response")*pl.col("building_value_real"))
        .when(pl.col("damage_type")=="content_loss").then(pl.col("expected_response")*pl.col("contents_value_real"))
        .when(pl.col("damage_type")=="loss_of_use").then(pl.col("expected_response")*pl.col("daily_relocation_real"))
        .otherwise(pl.col("expected_response")*pl.col("debris_area_sqft")/2000*pl.col("debris_cleanup_per_ton_real")))
        .select(k+["damage_type","expected_response","cost_real"]))
