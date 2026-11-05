"""Explicitly synthetic all-component demonstration; no production hazard claims."""
import argparse
import hashlib
import json
from pathlib import Path

import polars as pl

from .analysis import ROOT, AnalysisConfig, evaluate_analysis, publish_analysis
from .cashflows import KEYS, STREAMS
from .consequences import integrate_discrete_hazard, monetize_consequences
from .contents import contents_event_losses
from .contracts import ContractViolationError
from .disposal import attach_disposal, build_disposal_events, read_source_mass
from .pilot import pilot_options
from .reference import select_housing_rate
from .reporting import COMPONENTS
from .water import WaterParameters, interior_event_losses

# Bundled assumptions, not probability quantiles or calibrated material effects.
SCENARIOS = {
    "low": dict(rain_factor=0.5, breach_factor=0.5, capacity_factor=1.5,
                upstream_damage_factor=0.75, initial_rul_years=6,
                contents_value_real=30000., downtime_factor=0.5, eul_factor=0.9,
                maintenance_factor=0.5, real_discount_rate=0.01),
    "central": dict(rain_factor=1., breach_factor=1., capacity_factor=1.,
                    upstream_damage_factor=1., initial_rul_years=8,
                    contents_value_real=50000., downtime_factor=1., eul_factor=1.,
                    maintenance_factor=1., real_discount_rate=0.03),
    "high": dict(rain_factor=1.5, breach_factor=1.5, capacity_factor=0.5,
                 upstream_damage_factor=1.25, initial_rul_years=10,
                 contents_value_real=80000., downtime_factor=1.5, eul_factor=1.1,
                 maintenance_factor=1.5, real_discount_rate=0.05),
}


def demo_inputs(shared_root: Path, cadence_root: Path, assumption_set: str = "central", *,
                horizon: int = 30, discount_rate: float | None = None,
                overrides: dict | None = None):
    s = dict(SCENARIOS[assumption_set]) | (overrides or {})
    config = AnalysisConfig(horizon_years=horizon,
        real_discount_rate=s["real_discount_rate"] if discount_rate is None else discount_rate,
        base_dollar_year=2024, baseline_option_id="baseline", assumption_set_id=assumption_set,
        data_status="illustrative", source_version="synthetic_all_component_v1",
        roof_loss_scope="roof_exterior_only", water_loss_scope="separate_nonoverlapping",
        contents_loss_scope="separate_water_only", replacement_cost_scope="installed_excludes_disposal_and_damage",
        loss_of_use_scope="temporary_housing_before_insurance", event_policy="fixed_eul_pilot",
        overlap_method_id="synthetic_exterior_only_costs; new_water_channels_replace_any_HAZUS_interior_contents")
    options=pilot_options().with_columns(
        pl.col("option_id").replace_strict({"baseline":"BASELINE_CURRENT", "replace_asphalt_now":"NEW_ASPHALT", "upgrade_metal_now":"NEW_METAL"}).alias("scenario_id"),
        (pl.col("new_eul_years")*s["eul_factor"]).round(0).cast(pl.Int64).alias("new_eul_years"),
        pl.when(pl.col("option_id")=="baseline").then(int(round(s["initial_rul_years"])))
            .otherwise(pl.col("initial_rul_years")).alias("initial_rul_years"),
        pl.lit(2024).alias("base_dollar_year"),pl.lit("synthetic_installed_costs_and_fixed_EUL_v1").alias("source_version"),
    )
    annual=options.select(KEYS).join(pl.DataFrame({"offset":range(horizon)}),how="cross").with_columns(
        *[pl.lit(0.0).alias(c) for c in STREAMS],pl.lit(0.0).alias("interior_loss_real"),
        pl.lit(2024).alias("base_dollar_year"),pl.lit("synthetic_expected_consequences_v1").alias("source_version"),
    )
    mass_path=shared_root/"material_mass/roofing_lbs.csv"
    fees_path=shared_root/"disposal/EREF_2024_Tipping_Fees_Parsed.csv"
    housing_path=shared_root/"loss_of_use/temporary_housing_relocation_costs.csv"
    mass=read_source_mass(mass_path)
    removals=build_disposal_events(options,mass,fees_path,cadence_root,horizon)
    annual=attach_disposal(annual,removals)
    housing=select_housing_rate(housing_path,"37063",2025)
    # Explicit synthetic price conversion scenario: factor 1 is NOT observed CPI.
    housing=housing.with_columns(pl.lit(1.0).alias("source_to_base_factor"),pl.lit(2024).alias("base_dollar_year"),
        pl.lit("illustrative_equal_dollar_proxy_2025_to_2024; not_inflation_adjusted").alias("conversion_method_id"))
    params=WaterParameters(parameter_set_id=f"{assumption_set}_assumed_capacities",
        source_reference="Abreu_2019_p39_p42; footprint_capacities_are_assumed",
        covering_leakage_fraction=0.05,entry_efficiency=0.8,
        ceiling_capacity_l_per_m2=0.5*s["capacity_factor"],partitions_capacity_l_per_m2=0.3*s["capacity_factor"],
        contents_capacity_l_per_m2=1.0*s["capacity_factor"],floor_capacity_l_per_m2=0.2*s["capacity_factor"])
    storms=pl.DataFrame({"event_id":["no_storm","moderate","severe"],"wind_speed_mph":[0.,100.,140.],
        "probability_mass":[0.97,0.025,0.005],"effective_rain_mm":[0.,100.,250.],
        "cover_loss_fraction":[0.,0.08,0.35],"deck_breach_fraction":[0.,0.005,0.04],
        "roof_exterior_damage_ratio":[0.,0.08,0.35],"conditional_displacement_days":[0.,7.,45.]})
    support=annual.select(KEYS+["offset"]).join(options.select(KEYS+["initial_rul_years","material_id","roof_area_sqft","replacement_cost_real"]),on=KEYS,validate="m:1")
    # Explicit fixture assumption, not inferred fragility for asphalt or metal.
    support=support.with_columns(pl.when((pl.col("option_id")=="baseline") & (pl.col("offset")<pl.col("initial_rul_years")))
        .then(1.4).when(pl.col("option_id")=="upgrade_metal_now").then(0.4).otherwise(1.0).alias("fixture_damage_multiplier"))
    events=support.join(storms,how="cross").with_columns(
        (pl.col("decision_year")+pl.col("offset")).alias("year"),
        (pl.col("roof_area_sqft")*0.09290304).alias("roof_area_m2"),pl.lit(150.0).alias("wetted_area_m2"),
        (pl.col("effective_rain_mm")*s["rain_factor"]).alias("effective_rain_mm"),
        (pl.col("deck_breach_fraction")*pl.col("fixture_damage_multiplier")*s["breach_factor"]*s["upstream_damage_factor"]).clip(0,1).alias("deck_breach_fraction"),
        (pl.col("cover_loss_fraction")*pl.col("fixture_damage_multiplier")*s["breach_factor"]*s["upstream_damage_factor"]).clip(0,1).alias("cover_loss_fraction"),
        (pl.col("roof_exterior_damage_ratio")*pl.col("fixture_damage_multiplier")*s["upstream_damage_factor"]).clip(0,1).alias("roof_exterior_damage_ratio"),
        (pl.col("conditional_displacement_days")*pl.col("fixture_damage_multiplier")*s["downtime_factor"]).alias("conditional_displacement_days"),
        pl.lit(15000.).alias("ceiling_value_real"),pl.lit(25000.).alias("partitions_value_real"),
        pl.lit(15000.).alias("floor_value_real"),pl.lit(15000.).alias("cabinets_value_real"),
        pl.lit(10000.).alias("electrical_value_real"),pl.lit(s["contents_value_real"]).alias("contents_value_real"),
        pl.lit(2024).alias("base_dollar_year"),pl.lit("synthetic_joint_rain_roof_event_fixture_v1").alias("source_version"))
    water=contents_event_losses(interior_event_losses(events,params))
    hk=["asset_id","year","wind_speed_mph"]
    weights=water.select(hk+["probability_mass"]).unique().sort(hk)
    ck=["asset_id","year","option_id","wind_speed_mph"]
    responses=pl.concat([
        water.select(ck+[pl.lit("building_loss").alias("damage_type"),(pl.col("interior_loss_real")/80000.).alias("response_value")]),
        water.select(ck+[pl.lit("content_loss").alias("damage_type"),(pl.col("contents_loss_real")/s["contents_value_real"]).alias("response_value")]),
        water.select(ck+[pl.lit("loss_of_use").alias("damage_type"),pl.col("conditional_displacement_days").alias("response_value")])])
    expected=integrate_discrete_hazard(responses,weights)
    exposure=water.select(["asset_id","year","option_id"]).unique().with_columns(
        pl.lit(80000.).alias("building_value_real"),pl.lit(s["contents_value_real"]).alias("contents_value_real"),
        pl.lit(housing["relocation_cost_per_day"][0]).alias("daily_relocation_real"))
    money=monetize_consequences(expected,exposure).pivot(on="damage_type",index=["asset_id","year","option_id"],values="cost_real").rename(
        {"building_loss":"interior_loss_real","content_loss":"contents_loss_real","loss_of_use":"downtime_real"})
    roof_expected=integrate_discrete_hazard(water.select(ck+[pl.lit("building_loss").alias("damage_type"),
        pl.col("roof_exterior_damage_ratio").alias("response_value")]),weights)
    roof=roof_expected.join(options.select("asset_id","option_id","replacement_cost_real"),on=["asset_id","option_id"],validate="m:1").select(
        "asset_id","year","option_id",(pl.col("expected_response")*pl.col("replacement_cost_real")).alias("building_loss_real"))
    annual=annual.with_columns((pl.col("decision_year")+pl.col("offset")).alias("year")).drop(
        "building_loss_real","interior_loss_real","contents_loss_real","downtime_real").join(money,on=["asset_id","year","option_id"],validate="1:1").join(roof,on=["asset_id","year","option_id"],validate="1:1").with_columns(
        (pl.when(pl.col("option_id")=="upgrade_metal_now").then(80.).otherwise(120.)*s["maintenance_factor"]).alias("maintenance_real"))
    rows=[]
    sources={"replacement":"synthetic_2024_combined_installed_cost", "terminal_service_value":"synthetic_fixed_EUL_remaining_service_basis",
        "disposal":"EREF_2024_exact_mass_CADENCE_helper", "downtime":"synthetic_annual_days_times_HUD2025_illustrative_2024_proxy",
        "building_loss":"synthetic_roof_exterior_only", "interior_loss":"Abreu2019_eq2; assumed_entry_and_capacities",
        "contents_loss":"Abreu2019_eq3; assumed_inventory", "maintenance":"synthetic_annual_maintenance"}
    for key in options.select(KEYS).iter_rows(named=True):
        for c in list(COMPONENTS)+["interior_loss"]:
            rows.append(dict(**key,component=c,enabled=c in sources,source=sources.get(c,"explicitly_disabled"),
                source_year=2025 if c=="downtime" else 2019 if c in ("interior_loss","contents_loss") else 2024 if c in sources else None,
                valuation_method="illustrative; constant_2024_real; no_insurance; nonoverlapping_scope" if c in sources else "disabled"))
    metadata=pl.DataFrame(rows)
    tables=evaluate_analysis(options,annual,metadata,config)
    tables.update(event_water_damage=water, housing_reference=housing,
                  removal_event_costs=removals, hazard_mass_fixture=weights,
                  water_parameters=pl.DataFrame([params.model_dump()]),assumptions=pl.DataFrame([s]))
    # Add removed material/event economics to the generated schedule using actual events.
    tables["replacement_events"]=tables["replacement_events"].join(removals.select(KEYS+["offset","removed_material_id","roof_area_sqft","removed_roof_mass_lbs","disposal_real"]),on=KEYS+["offset"],validate="1:1")
    identities={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [mass_path,fees_path,housing_path,
        *[cadence_root/f"src/cadence/economics/{n}.py" for n in ("contracts","materials","externalities")]]}
    identities["thesis_sha256"]="ad1a7e68564bb1af20ab3d7b8308dcc1eb6cbd1622c81975556ef5fb51b368d2"
    return tables,config,identities


def run_demo(shared_root: Path, cadence_root: Path, output_root: Path, *, horizon=30, discount_rate=None,
             sensitivity=False, samples=0, seed=20261104):
    paths=[]
    sensitivity_table=None
    if sensitivity or samples:
        from .sensitivity import evaluate_sensitivity
        sensitivity_table=evaluate_sensitivity(shared_root,cadence_root,horizon=horizon,samples=samples,seed=seed)
    for name in SCENARIOS:
        tables,config,sources=demo_inputs(shared_root,cadence_root,name,horizon=horizon,discount_rate=discount_rate)
        if sensitivity_table is not None:
            tables["sensitivity_results"]=sensitivity_table
        path=publish_analysis(output_root,tables,config,sources)
        paths.append(path)
        print(f"{name}: {path}")
        print(tables["lifecycle_summary"].select("option_id","npc_real","incremental_npv_real","investment_rank"))
    return paths


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir",type=Path,help="Supplied options.parquet, annual_costs.parquet, component_metadata.parquet and config.json")
    parser.add_argument("--shared-root",type=Path,default=ROOT.parent/"cadence_shared_data/reference_data")
    parser.add_argument("--cadence-root",type=Path,default=ROOT.parent/"CADENCE")
    parser.add_argument("--output-root",type=Path,default=ROOT/"outputs/full_lifecycle")
    parser.add_argument("--horizon",type=int,default=30)
    parser.add_argument("--discount-rate",type=float)
    parser.add_argument("--sensitivity",action="store_true",help="Include one-at-a-time parameter endpoint scenarios")
    parser.add_argument("--samples",type=int,default=0,help="Additional reproducible assumed triangular joint draws")
    parser.add_argument("--seed",type=int,default=20261104)
    args=parser.parse_args()
    if args.input_dir:
        root=args.input_dir
        config=AnalysisConfig.model_validate_json((root/"config.json").read_text())
        tables_in={name:pl.read_parquet(root/f"{name}.parquet") for name in ["options","annual_costs","component_metadata"]}
        kwargs={}
        if config.event_policy=="upstream_events_and_terminal":
            kwargs={name:pl.read_parquet(root/f"{name}.parquet") for name in ["replacement_events","terminal_values"]}
        tables=evaluate_analysis(tables_in["options"],tables_in["annual_costs"],tables_in["component_metadata"],config,**kwargs)
        sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file() and p.suffix in (".parquet",".json")}
        print(publish_analysis(args.output_root,tables,config,sources))
    else:
        if args.samples < 0:
            parser.error("--samples cannot be negative")
        run_demo(args.shared_root,args.cadence_root,args.output_root,horizon=args.horizon,discount_rate=args.discount_rate,
                 sensitivity=args.sensitivity,samples=args.samples,seed=args.seed)


if __name__=="__main__":
    main()
