"""Annual lifecycle accounting, one baseline per asset and decision year."""
import polars as pl
from .contracts import ContractViolationError, require_columns, require_unique
from .replacement import project_fixed_eul_events, terminal_residual

KEYS=["asset_id","decision_year","option_id"]
STREAMS=["maintenance_real","building_loss_real","contents_loss_real","downtime_real","debris_brick_wood_real","debris_concrete_steel_real","disposal_real","salvage_credit_real"]

def build_cashflows(options: pl.DataFrame, annual_costs: pl.DataFrame, horizon_years: int=30, real_discount_rate: float=0.03) -> pl.DataFrame:
    """Build real-dollar year-end operating flows and terminal credit at t=horizon.

    Annual-cost input must contain every named stream, explicitly zero for
    disabled streams. A separate flag/config is required upstream to distinguish
    disabled from unobserved data. Replacement event costs are paid at t=offset.
    """
    if real_discount_rate <= -1:
        raise ContractViolationError("discount rate must exceed -100%")
    require_columns(annual_costs, KEYS+["offset"]+STREAMS, "annual_costs")
    require_unique(annual_costs, KEYS+["offset"], "annual_costs")
    require_unique(options, KEYS, "options")
    expected=options.select(KEYS).join(pl.DataFrame({"offset":range(horizon_years)}),how="cross")
    costs=expected.join(annual_costs,on=KEYS+["offset"],how="left",validate="1:1")
    if costs.select(pl.any_horizontal(*[pl.col(c).is_null() for c in STREAMS])).to_series().any():
        raise ContractViolationError("annual cost rows incomplete; never silently fill missing costs")
    events=project_fixed_eul_events(options,horizon_years).group_by(KEYS+["offset"]).agg(pl.col("event_cost_real").sum().alias("replacement_real"))
    costs=costs.join(events,on=KEYS+["offset"],how="left").with_columns(pl.col("replacement_real").fill_null(0))
    costs=costs.with_columns(total_real=(pl.sum_horizontal(*[pl.col(c) for c in STREAMS if c!="salvage_credit_real"],pl.col("replacement_real"))-pl.col("salvage_credit_real")))
    costs=costs.with_columns(discounted_real=pl.col("total_real")/(1+real_discount_rate)**pl.col("offset"), financial_year=pl.col("decision_year")+pl.col("offset"))
    residual=terminal_residual(options,horizon_years).with_columns(offset=pl.lit(horizon_years),financial_year=pl.col("decision_year")+horizon_years,total_real=-pl.col("terminal_value_real"),discounted_real=-pl.col("terminal_value_real")/(1+real_discount_rate)**horizon_years)
    for col in STREAMS+["replacement_real"]:
        residual=residual.with_columns(pl.lit(0.0).alias(col))
    return pl.concat([costs.select(KEYS+["offset","financial_year"]+STREAMS+["replacement_real","total_real","discounted_real"]),residual.select(KEYS+["offset","financial_year"]+STREAMS+["replacement_real","total_real","discounted_real"])],how="vertical").sort(KEYS+["offset"])

def compare_options(cashflows: pl.DataFrame, baseline_option_id: str="baseline") -> pl.DataFrame:
    require_columns(cashflows, KEYS+["discounted_real"], "cashflows")
    summary=cashflows.group_by(KEYS).agg(pl.col("discounted_real").sum().alias("npc_real"))
    base=(summary.filter(pl.col("option_id")==baseline_option_id).select("asset_id","decision_year",pl.col("npc_real").alias("baseline_npc_real")))
    require_unique(base,["asset_id","decision_year"],"baseline")
    if base.height != summary.select("asset_id","decision_year").unique().height:
        raise ContractViolationError("exactly one baseline required per asset/decision year")
    return summary.join(base,on=["asset_id","decision_year"],how="left",validate="m:1").with_columns(incremental_npv_real=pl.col("baseline_npc_real")-pl.col("npc_real"))
