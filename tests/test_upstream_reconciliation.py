"""Compare actual read-only CADENCE economics on equivalent supplied inputs."""
import polars as pl
import pytest

from cadence_lifecycle.analysis import AnalysisConfig, ROOT, evaluate_analysis
from cadence_lifecycle.cadence_exchange import adapt_cadence_analysis
from cadence_lifecycle.cashflows import KEYS, STREAMS
from cadence_lifecycle.reporting import COMPONENTS
from cadence_lifecycle.upstream import evaluate_upstream_economics


def test_actual_cadence_npv_matches_supplied_events_no_terminal_policy():
    cadence=ROOT.parent/"CADENCE"
    if not (cadence/"src/cadence/economics/alternative_analysis.py").exists():
        pytest.skip("Read-only CADENCE source unavailable")
    classes=["OFFICIAL_ASPHALT","OFFICIAL_METAL","OFFICIAL_TILE"]
    config=dict(installed_cost_overrides={c:dict(installed_usd_per_sqft=10.,material_share=.6,labor_share=.4) for c in classes},
        default_roof_shape="gable",default_roof_deck_attachment="8d_6in_12in",default_roof_wall_connection="strap",
        real_discount_rate=.02)
    scenarios=pl.DataFrame(dict(scenario_id=["BASELINE_CURRENT","NEW_ASPHALT","NEW_METAL","NEW_TILE"],
        scenario_role=["installed_baseline"]+["new_alternative"]*3,
        scenario_material_id=[classes[0]]+classes))
    state=pl.DataFrame(dict(year=[2026,2027],asset_id=["A-1"]*2)).join(scenarios,how="cross").with_columns(
        ((pl.col("year")==2026)&(pl.col("scenario_role")=="new_alternative")).alias("installation_event"),
        pl.lit("OFFICIAL_ASPHALT").alias("removed_material_id"))
    damage=state.select("asset_id","year","scenario_id").with_columns(
        pl.when(pl.col("scenario_id")=="BASELINE_CURRENT").then(.2).otherwise(.05).alias("expected_damage_ratio"))
    costs=state.select("asset_id","year",pl.col("scenario_material_id").alias("official_material_id")).unique().with_columns(
        pl.lit(1000.).alias("roof_area_sqft"),pl.lit(10000.).alias("installed_capex_usd"),
        pl.lit("synthetic_fixture").alias("operational_cost_source"),pl.lit(False).alias("operational_cost_fallback_applied"))
    upstream=evaluate_upstream_economics(cadence,state,damage,costs,config)
    rest=[c for c in STREAMS if c not in ["building_loss_real","downtime_real","disposal_real"]]+["interior_loss_real"]
    supplements=upstream.select("asset_id","year","scenario_id").with_columns(
        *[pl.lit(0.).alias(c) for c in rest],pl.lit(2026).alias("base_dollar_year"))
    cfg=AnalysisConfig(horizon_years=2,real_discount_rate=.02,base_dollar_year=2026,baseline_option_id="BASELINE_CURRENT",
        assumption_set_id="source_reconciliation",data_status="illustrative",source_version="actual_CADENCE_on_synthetic_inputs",
        roof_loss_scope="roof_exterior_only",water_loss_scope="disabled",contents_loss_scope="disabled",
        replacement_cost_scope="installed_excludes_disposal_and_damage",loss_of_use_scope="disabled",
        event_policy="upstream_events_and_terminal",overlap_method_id="synthetic_separate_roof_only")
    adapted=adapt_cadence_analysis(upstream,supplements,cfg,decision_year=2026,source_version="actual_source_fixture",terminal_policy="none")
    metadata=pl.DataFrame([dict(**k,component=c,enabled=c in ["replacement","building_loss"],source="actual_source_fixture",
        source_year=2026,valuation_method="no_terminal_credit; identical_annual_costs")
        for k in adapted["options"].select(KEYS).iter_rows(named=True) for c in list(COMPONENTS)+["interior_loss"]])
    result=evaluate_analysis(adapted["options"],adapted["annual_costs"],metadata,cfg,
        replacement_events=adapted["replacement_events"],terminal_values=adapted["terminal_values"])
    expected=upstream.filter(pl.col("year")==2027).select("scenario_id","net_present_value_usd")
    compare=result["lifecycle_summary"].join(expected,on="scenario_id",validate="1:1")
    assert compare["incremental_npv_real"].to_list()==pytest.approx(compare["net_present_value_usd"].to_list())
