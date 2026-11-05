"""Translate verified CADENCE annual-analysis fields without rebuilding state."""
import polars as pl

from .analysis import AnalysisConfig
from .cashflows import KEYS, STREAMS
from .contracts import ContractViolationError, require_columns, require_unique
from .disposal import require_finite

UPSTREAM_KEYS = ["asset_id", "year", "scenario_id"]


def adapt_cadence_analysis(upstream: pl.DataFrame, supplements: pl.DataFrame,
                          config: AnalysisConfig, *, decision_year: int,
                          source_version: str, terminal_policy: str) -> dict[str, pl.DataFrame]:
    """Consume annual_alternative_analysis; identity option_id = scenario_id.

    No probabilities, costs, states or material mappings are recalculated.
    Supplements explicitly provide every remaining stream at upstream annual
    grain, including zero for disabled ones. Dollar conversion must occur before
    this adapter; the inspected CADENCE export declares real_2026_usd.
    terminal_policy='none' matches inspected CADENCE's absent residual credit.
    Other terminal policies require independently supplied terminal_values via
    evaluate_analysis, rather than an inferred basis here.
    """
    if config.event_policy != "upstream_events_and_terminal" or terminal_policy != "none":
        raise ContractViolationError("Explicit upstream event policy and no-credit terminal policy required")
    if not source_version.strip():
        raise ContractViolationError("Upstream source identity required")
    cols=["scenario_material_id", "removed_material_id", "installation_event", "roof_area_sqft",
          "annual_repair_cost_usd", "installation_event_capex_usd", "enabled_event_disposal_cost_usd",
          "enabled_event_carbon_cost_usd", "dollar_basis"]
    require_unique(upstream,UPSTREAM_KEYS,"CADENCE annual analysis")
    require_columns(upstream,cols,"CADENCE annual analysis")
    if upstream.is_empty() or upstream.filter(pl.col("dollar_basis").is_null()
            | (pl.col("dollar_basis") != f"real_{config.base_dollar_year}_usd")).height:
        raise ContractViolationError("CADENCE monetary source year must match the requested dollar base")
    for flag in ["repair_cost_incomplete","climate_risk_total_incomplete","event_cost_incomplete"]:
        if flag in upstream.columns and upstream.filter(pl.col(flag).is_null() | pl.col(flag)).height:
            raise ContractViolationError(f"Incomplete CADENCE history: {flag}")
    numeric=["year","roof_area_sqft","annual_repair_cost_usd","installation_event_capex_usd",
             "enabled_event_disposal_cost_usd","enabled_event_carbon_cost_usd"]
    if config.loss_of_use_scope != "disabled":
        numeric.append("expected_loss_of_use_usd")
    require_finite(upstream,numeric,"CADENCE economic inputs")
    if upstream.filter((pl.col("enabled_event_carbon_cost_usd") != 0)
            | (pl.col("year") < decision_year) | (pl.col("year") >= decision_year+config.horizon_years)
            | (pl.col("year") != pl.col("year").floor())
            | (pl.col("roof_area_sqft") <= 0)).height:
        raise ContractViolationError("Unsupported carbon stream, year support or area")
    rest=[c for c in STREAMS if c not in ["building_loss_real","downtime_real","disposal_real"]]+["interior_loss_real"]
    require_unique(supplements,UPSTREAM_KEYS,"supplemental annual costs")
    require_finite(supplements,rest+["base_dollar_year"],"supplemental annual costs")
    if supplements.filter(pl.col("base_dollar_year")!=config.base_dollar_year).height:
        raise ContractViolationError("Supplemental dollar year mismatch")
    if (upstream.join(supplements.select(UPSTREAM_KEYS),on=UPSTREAM_KEYS,how="anti").height
            or supplements.join(upstream.select(UPSTREAM_KEYS),on=UPSTREAM_KEYS,how="anti").height):
        raise ContractViolationError("Supplemental costs must exactly cover upstream annual history")
    normalized=upstream.with_columns(
        pl.col("scenario_id").alias("option_id"),pl.lit(decision_year).alias("decision_year"),
        (pl.col("year")-decision_year).alias("offset"),pl.lit(config.base_dollar_year).alias("base_dollar_year"),
        pl.lit(source_version).alias("source_version"))
    options=normalized.select(KEYS+["scenario_id","base_dollar_year","source_version"]).unique().sort(KEYS)
    annual=normalized.select(KEYS+["year","scenario_id","offset","base_dollar_year","source_version",
        pl.col("annual_repair_cost_usd").alias("building_loss_real"),
        pl.col("enabled_event_disposal_cost_usd").alias("disposal_real"),
        (pl.lit(0.) if config.loss_of_use_scope=="disabled" else pl.col("expected_loss_of_use_usd")).alias("downtime_real")]
    ).join(supplements.select(UPSTREAM_KEYS+rest),on=UPSTREAM_KEYS,validate="1:1")
    if normalized.filter(pl.col("installation_event").is_null()
            | (~pl.col("installation_event") & ((pl.col("installation_event_capex_usd")!=0)
              | (pl.col("enabled_event_disposal_cost_usd")!=0)))).height:
        raise ContractViolationError("Capital/disposal costs must correspond to actual removal events")
    events=normalized.filter(pl.col("installation_event")).select(KEYS+[
        "offset",pl.col("year").alias("event_year"),"base_dollar_year","source_version","removed_material_id",
        pl.col("scenario_material_id").alias("material_id"),"roof_area_sqft",
        pl.col("installation_event_capex_usd").alias("event_cost_real")])
    terminal=options.with_columns(pl.lit(0.).alias("terminal_value_real"),
        pl.lit("none; match_CADENCE_no_terminal_credit").alias("terminal_policy"))
    return dict(options=options,annual_costs=annual,replacement_events=events,terminal_values=terminal)
