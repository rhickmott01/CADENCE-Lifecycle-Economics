"""Vectorized fixed-EUL pilot. Production RUL transition is CADENCE-owned."""
import polars as pl
from .contracts import ContractViolationError, require_columns, require_unique, REQUIRED_ASSET

def project_fixed_eul_events(options: pl.DataFrame, horizon_years: int = 30) -> pl.DataFrame:
    """Return replacement events in [decision_year, decision_year+horizon_years).

    initial_rul_years=0 means replacement immediately. Replacement at the
    terminal boundary is excluded; terminal value is evaluated there instead.
    All alternatives must include a baseline option supplied by the caller.
    """
    require_columns(options, REQUIRED_ASSET, "options")
    require_unique(options, ["asset_id", "decision_year", "option_id"], "options")
    if not isinstance(horizon_years, int) or isinstance(horizon_years, bool) or horizon_years < 1:
        raise ContractViolationError("horizon must be positive")
    numeric=["initial_rul_years", "new_eul_years", "replacement_cost_real", "roof_area_sqft", "decision_year"]
    if options.is_empty() or options.filter(pl.any_horizontal(*[
        pl.col(c).is_null() | ~pl.col(c).is_finite() for c in numeric
    ]) | pl.any_horizontal(*[pl.col(c).is_null() for c in ["asset_id", "option_id", "material_id"]])
       | (pl.col("initial_rul_years") != pl.col("initial_rul_years").floor())
       | (pl.col("new_eul_years") != pl.col("new_eul_years").floor())
       | (pl.col("decision_year") != pl.col("decision_year").floor())).height:
        raise ContractViolationError("Complete finite values and integer schedule years required")
    bad = options.filter((pl.col("initial_rul_years") < 0) | (pl.col("new_eul_years") <= 0) | (pl.col("replacement_cost_real") < 0) | (pl.col("roof_area_sqft") <= 0) | pl.any_horizontal(pl.col("initial_rul_years").is_null(),pl.col("new_eul_years").is_null(),pl.col("replacement_cost_real").is_null()))
    if bad.height:
        raise ContractViolationError("invalid RUL, EUL, area or replacement cost")
    # Cross join small time-index dimension; all asset-option math is Polars.
    years = pl.DataFrame({"offset": range(horizon_years)})
    return (options.join(years, how="cross")
      .filter((pl.col("offset") >= pl.col("initial_rul_years")) &
              (((pl.col("offset")-pl.col("initial_rul_years")) % pl.col("new_eul_years")) == 0))
      .with_columns(event_year=pl.col("decision_year")+pl.col("offset"),
                    event_type=pl.when(pl.col("offset")==0).then(pl.lit("immediate")).otherwise(pl.lit("burnout_or_repeat")),
                    event_cost_real=pl.col("replacement_cost_real"))
      .select("asset_id","decision_year","option_id","material_id","event_year","offset","event_type","event_cost_real"))

def terminal_residual(options: pl.DataFrame, horizon_years: int=30) -> pl.DataFrame:
    """Straight-line unconsumed service value at terminal boundary.

    For options where the first replacement has not occurred by the horizon,
    the existing roof's eligible residual basis must be provided separately as
    existing_roof_basis_real; new-roof replacement price is not a valid proxy.
    """
    require_columns(options, REQUIRED_ASSET | {"existing_roof_basis_real", "existing_eul_years"}, "options")
    project_fixed_eul_events(options, horizon_years)  # apply the same scheduling input contract
    if options.filter(pl.any_horizontal(*[pl.col(c).is_null() | ~pl.col(c).is_finite()
                for c in ["existing_roof_basis_real", "existing_eul_years"]])
                | (pl.col("initial_rul_years") > pl.col("existing_eul_years"))).height:
        raise ContractViolationError("Invalid existing roof remaining-life/basis support")
    if options.filter((pl.col("existing_roof_basis_real")<0)|(pl.col("existing_eul_years")<=0)).height:
        raise ContractViolationError("invalid existing roof basis/EUL")
    h=pl.lit(horizon_years)
    first=pl.col("initial_rul_years")
    eul=pl.col("new_eul_years")
    elapsed=h-first
    remaining_new=pl.when(elapsed>0).then((eul-1-((elapsed-1)%eul)).clip(lower_bound=0)).otherwise(pl.lit(0))
    remaining_existing=(first-h).clip(lower_bound=0)
    return options.select("asset_id","decision_year","option_id",
      pl.when(first>=h).then(pl.col("existing_roof_basis_real")*remaining_existing/pl.col("existing_eul_years"))
      .otherwise(pl.col("replacement_cost_real")*remaining_new/eul)
      .alias("terminal_value_real"))
