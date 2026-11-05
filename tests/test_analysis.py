import json
from pathlib import Path

import duckdb
import polars as pl
import pytest

from cadence_lifecycle.analysis import AnalysisConfig, ROOT, evaluate_analysis, publish_analysis, validate_exchange_tables
from cadence_lifecycle.cashflows import KEYS, STREAMS
from cadence_lifecycle.contracts import ContractViolationError
from cadence_lifecycle.demo import demo_inputs
from cadence_lifecycle.reporting import COMPONENTS


@pytest.fixture
def inputs():
    options=pl.DataFrame(dict(asset_id=["a"]*2,decision_year=[2026]*2,option_id=["baseline","upgrade"],
        scenario_id=["BASELINE_CURRENT","NEW_METAL"],source_version=["fixture"]*2,
        base_dollar_year=[2024]*2,county_fips=["01001"]*2))
    annual=options.select(KEYS).join(pl.DataFrame({"offset":[0,1]}),how="cross").with_columns(
        *[pl.lit(0.).alias(c) for c in STREAMS],pl.lit(2024).alias("base_dollar_year"),pl.lit("fixture").alias("source_version"),
        pl.when(pl.col("option_id")=="baseline").then(10.).otherwise(0.).alias("interior_loss_real"))
    annual=annual.with_columns(
        pl.when(pl.col("option_id")=="baseline").then(100.).otherwise(50.).alias("maintenance_real"),
        pl.when(pl.col("option_id")=="baseline").then(20.).otherwise(0.).alias("contents_loss_real"))
    events=options.filter(pl.col("option_id")=="upgrade").with_columns(offset=pl.lit(0),event_cost_real=pl.lit(100.),
        removed_material_id=pl.lit("old"),material_id=pl.lit("new"))
    terminal=options.with_columns(terminal_value_real=pl.lit(0.))
    config=AnalysisConfig(horizon_years=2,real_discount_rate=0.1,base_dollar_year=2024,baseline_option_id="baseline",
        assumption_set_id="fixture",data_status="illustrative",source_version="fixture",
        roof_loss_scope="roof_exterior_only",water_loss_scope="separate_nonoverlapping",contents_loss_scope="separate_water_only",
        replacement_cost_scope="installed_excludes_disposal_and_damage",loss_of_use_scope="disabled",
        event_policy="upstream_events_and_terminal",overlap_method_id="fixture_separate_components")
    metadata=pl.DataFrame([dict(**key,component=c,enabled=c in ["maintenance","contents_loss","interior_loss","replacement"],
        source="fixture",source_year=2024,valuation_method="synthetic")
        for key in options.select(KEYS).iter_rows(named=True) for c in list(COMPONENTS)+["interior_loss"]])
    return options,annual,metadata,config,events,terminal


def evaluate(inputs, **changes):
    options,annual,metadata,config,events,terminal=inputs
    return evaluate_analysis(changes.get("options",options),changes.get("annual",annual),changes.get("metadata",metadata),
        changes.get("config",config),replacement_events=changes.get("events",events),terminal_values=changes.get("terminal",terminal))


def test_independent_discounted_npv_and_component_reconciliation(inputs):
    tables=evaluate(inputs)
    result=tables["lifecycle_summary"].filter(pl.col("option_id")=="upgrade")
    # $80 avoided each year, $100 immediate installation, no terminal value.
    assert result["incremental_npv_real"][0] == pytest.approx(80+80/1.1-100)
    report=tables["npv_contributions"].filter(pl.col("option_id")=="upgrade")
    assert report["npv_contribution_real"].sum() == pytest.approx(result["incremental_npv_real"][0])
    assert report.filter(pl.col("component")=="interior_loss")["npv_contribution_real"][0] == pytest.approx(10+10/1.1)
    assert tables["options"]["county_fips"].to_list() == ["01001"]*2


@pytest.mark.parametrize("case",["missing_year","nonfinite","extra_year","missing_source","double_interior",
    "disabled_interior","wrong_base","duplicate_crosswalk","terminal_missing","events_wrong_base","metadata_disabled"])
def test_incomplete_or_overlapping_inputs_fail_closed(inputs,case):
    options,annual,metadata,config,events,terminal=inputs
    changes={}
    if case=="missing_year":changes["annual"]=annual.head(3)
    elif case=="nonfinite":changes["annual"]=annual.with_columns(maintenance_real=pl.lit(float("nan")))
    elif case=="extra_year":changes["annual"]=pl.concat([annual,annual.head(1).with_columns(offset=pl.lit(99))],how="vertical_relaxed")
    elif case=="missing_source":changes["annual"]=annual.with_columns(source_version=pl.lit(""))
    elif case=="double_interior":changes["config"]=config.model_copy(update=dict(roof_loss_scope="aggregate_building_including_interior"))
    elif case=="disabled_interior":changes["config"]=config.model_copy(update=dict(water_loss_scope="disabled"))
    elif case=="wrong_base":changes["annual"]=annual.with_columns(base_dollar_year=pl.lit(2025))
    elif case=="duplicate_crosswalk":changes["options"]=options.with_columns(scenario_id=pl.lit("same"))
    elif case=="terminal_missing":changes["terminal"]=terminal.head(1)
    elif case=="events_wrong_base":changes["events"]=events.with_columns(base_dollar_year=pl.lit(2025))
    else:changes["metadata"]=metadata.with_columns(enabled=pl.lit(False))
    with pytest.raises(ContractViolationError):evaluate(inputs,**changes)


def test_parquet_schema_join_reproducibility_and_write_once(inputs):
    import tempfile
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        directory=Path(directory)
        tables=evaluate(inputs)
        first=publish_analysis(directory/"first",tables,inputs[3],{"fixture":"v1"},chart=False)
        second=publish_analysis(directory/"second",tables,inputs[3],{"fixture":"v1"},chart=False)
        assert first.name==second.name
        for p in first.iterdir():assert p.read_bytes()==(second/p.name).read_bytes()
        flow=pl.read_parquet(first/"annual_lifecycle_cashflows.parquet")
        assert flow["run_id"].n_unique()==1
        assert {"scenario_id","source","source_year","valuation_method","completeness_status"} <= set(flow.columns)
        with duckdb.connect() as db:
            db.read_parquet(str(first/"options.parquet")).create_view("o")
            assert db.sql("select county_fips from o limit 1").fetchone()[0]=="01001"
        schema=json.loads((first/"schemas.json").read_text())
        assert schema["annual_lifecycle_cashflows"]["columns"]["scenario_id"]=="String"
        with pytest.raises(ContractViolationError,match="write-once"):
            publish_analysis(directory/"first",tables,inputs[3],{"fixture":"v1"},chart=False)


def test_all_five_components_with_real_reference_anchors():
    shared=ROOT.parent/"cadence_shared_data/reference_data"
    cadence=ROOT.parent/"CADENCE"
    if not shared.exists() or not (cadence/"src/cadence/economics/externalities.py").exists():
        pytest.skip("Read-only sibling references unavailable")
    tables,_,_=demo_inputs(shared,cadence,horizon=3)
    report=tables["npv_contributions"]
    for component in ["replacement","maintenance","downtime","disposal","interior_loss","contents_loss"]:
        assert report.filter(pl.col("component")==component)["option_pv_real"].max()>0
    zero=tables["event_water_damage"].filter(pl.col("event_id")=="no_storm")
    assert zero["water_entry_l"].sum()==zero["interior_loss_real"].sum()==zero["contents_loss_real"].sum()==0
    removal=tables["replacement_events"]
    assert removal["removed_material_id"].unique().to_list()==["Architectural Asphalt Shingles"]
    assert removal["disposal_real"].to_list()==pytest.approx([99.275,99.275])


def test_export_validator_rejects_tampered_financial_totals(inputs):
    tables=evaluate(inputs)
    tables["lifecycle_summary"]=tables["lifecycle_summary"].with_columns(npc_real=pl.col("npc_real")+1)
    with pytest.raises(ContractViolationError,match="reconcile"):
        validate_exchange_tables(tables)


def test_validated_status_does_not_promote_synthetic_inputs(inputs):
    config=inputs[3].model_copy(update={"data_status":"upstream_validated"})
    with pytest.raises(ContractViolationError,match="validation_status"):
        evaluate(inputs,config=config)
