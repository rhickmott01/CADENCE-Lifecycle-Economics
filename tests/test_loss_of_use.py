from pathlib import Path

import polars as pl
import pytest
from pydantic import ValidationError

from cadence_lifecycle.cashflows import KEYS, STREAMS, build_cashflows
from cadence_lifecycle.contracts import ContractViolationError
from cadence_lifecycle.loss_of_use import (
    HOUSING_SCOPE, HousingDollarBasis, attach_loss_of_use, build_loss_of_use_costs, loss_of_use_metadata,
)
from cadence_lifecycle.pilot import pilot_metadata, pilot_options
from cadence_lifecycle.reporting import build_component_report


@pytest.fixture
def inputs(tmp_path):
    options=pilot_options().filter(pl.col("option_id") != "replace_asphalt_now")
    annual=options.select(KEYS).join(pl.DataFrame({"offset":range(3)}),how="cross")
    annual=annual.with_columns(*[pl.lit(0.0).alias(c) for c in STREAMS])
    days=annual.select(KEYS+["offset"]).with_columns(
        expected_loss_of_use_days=pl.when(pl.col("option_id")=="baseline").then(2.0).otherwise(1.0),
        hazard_method_id=pl.lit("fixture_hazard"), curve_mapping_id=pl.lit("fixture_mapping"),
        source_version=pl.lit("synthetic_test_expectations"), validation_status=pl.lit("approved"),
        day_allocation_method=pl.lit("unique_away_days_within_financial_year"),
    )
    assets=pl.DataFrame({"asset_id":["house_001"],"county_fips":["01001"],"bedroom":["Two-Bedroom"]})
    housing=tmp_path/"housing.csv"
    pl.DataFrame({"county_fips":["01001"],"year":[2025],"primary_bedroom":["Two-Bedroom"],
                  "relocation_cost_per_day":[100.0],"daily_two_bedroom":[100.0],"daily_three_bedroom":[150.0]}).write_csv(housing)
    # Explicit synthetic conversion tests mechanics, not an approved real-world index.
    basis=HousingDollarBasis(source_year=2025,base_year=2026,factor=1.1,source_period="test-2025",
                            base_period="test-2026",method_id="synthetic_test_index",source_reference="test fixture")
    return options,annual,days,assets,housing,basis


def test_annual_housing_costs_reuse_days_monetization_and_preserve_basis(inputs):
    _,_,days,assets,housing,basis=inputs
    costs=build_loss_of_use_costs(days,assets,housing,basis)
    assert costs.filter(pl.col("option_id")=="baseline")["downtime_real"].to_list()==pytest.approx([220]*3)
    assert costs.filter(pl.col("option_id")=="upgrade_metal_now")["downtime_real"].to_list()==pytest.approx([110]*3)
    assert costs["base_dollar_year"].unique().to_list()==[2026]
    assert costs["county_fips"].unique().to_list()==["01001"]
    assert costs["source_year"].unique().to_list()==[2025]
    assert costs["source_to_base_factor"].unique().to_list()==[1.1]
    assert costs["daily_relocation_real"].n_unique()==1  # no assumed real rent growth


@pytest.mark.parametrize("same_days",[False,True])
def test_loss_of_use_npv_reconciles_through_existing_report(inputs,same_days):
    options,annual,days,assets,housing,basis=inputs
    if same_days:
        days=days.with_columns(expected_loss_of_use_days=pl.lit(1.0))
    costs=build_loss_of_use_costs(days,assets,housing,basis)
    annual=attach_loss_of_use(annual,costs,base_dollar_year=2026)
    metadata=pl.concat([
        pilot_metadata(options).filter(pl.col("component")!="downtime"),
        loss_of_use_metadata(costs),
    ],how="diagonal_relaxed")
    report=build_component_report(build_cashflows(options,annual,3,0.1),metadata,2026)
    row=report.filter((pl.col("option_id")=="upgrade_metal_now") & (pl.col("component")=="downtime"))
    expected=0 if same_days else 110+110/1.1+110/1.1**2
    assert row["npv_contribution_real"][0]==pytest.approx(expected)


def test_different_bedroom_tier_uses_its_own_published_rate(inputs):
    _,_,days,assets,housing,basis=inputs
    costs=build_loss_of_use_costs(days,assets.with_columns(bedroom=pl.lit("Three-Bedroom")),housing,basis)
    assert costs["relocation_cost_per_day"].unique().to_list()==[150.0]
    assert costs["daily_relocation_real"].unique().to_list()==[165.0]


def test_distinct_decision_years_do_not_collide_in_monetization(inputs):
    _,_,days,assets,housing,basis=inputs
    days=pl.concat([days,days.with_columns(decision_year=pl.lit(2027,dtype=pl.Int64))])
    costs=build_loss_of_use_costs(days,assets,housing,basis)
    assert costs.height==12
    assert costs["downtime_real"].sum()==pytest.approx(1980)


@pytest.mark.parametrize("case",["negative","nonfinite","null","unapproved","missing_source","raw_long_duration"])
def test_unsupported_displacement_is_not_silently_monetized(inputs,case):
    _,_,days,assets,housing,basis=inputs
    if case in ["negative","nonfinite","null","raw_long_duration"]:
        value={"negative":-1.0,"nonfinite":float("nan"),"null":None,"raw_long_duration":720.0}[case]
        days=days.with_columns(expected_loss_of_use_days=pl.lit(value,dtype=pl.Float64))
    elif case=="unapproved":
        days=days.with_columns(validation_status=pl.lit("pending"))
    else:
        days=days.drop("curve_mapping_id")
    with pytest.raises(ContractViolationError):
        build_loss_of_use_costs(days,assets,housing,basis)


@pytest.mark.parametrize("case",["missing_year","double_charge","wrong_base","unapproved","nonfinite","discounted","wrong_scope"])
def test_annual_cost_attachment_is_complete_sourced_and_once_only(inputs,case):
    _,annual,days,assets,housing,basis=inputs
    costs=build_loss_of_use_costs(days,assets,housing,basis)
    if case=="missing_year":costs=costs.head(costs.height-1)
    elif case=="double_charge":annual=annual.with_columns(downtime_real=pl.lit(1.0))
    elif case=="wrong_base":costs=costs.with_columns(base_dollar_year=pl.lit(2025))
    elif case=="unapproved":costs=costs.with_columns(validation_status=pl.lit("pending"))
    elif case=="discounted":costs=costs.with_columns(discount_status=pl.lit("discounted"))
    elif case=="wrong_scope":costs=costs.with_columns(cost_scope=pl.lit("net_of_insurance"))
    else:costs=costs.with_columns(downtime_real=pl.lit(float("nan")))
    with pytest.raises(ContractViolationError):
        attach_loss_of_use(annual,costs,base_dollar_year=2026)


@pytest.mark.parametrize("factor",[0,-1,float("nan"),float("inf")])
def test_invalid_price_conversion_factors_are_blocked(inputs,factor):
    basis=inputs[-1]
    with pytest.raises(ValidationError):
        HousingDollarBasis(**{**basis.model_dump(),"factor":factor})


def test_upstream_valued_costs_are_attached_without_another_conversion(inputs):
    _,annual,_,_,_,_=inputs
    costs=annual.select(KEYS+["offset"]).with_columns(
        downtime_real=pl.lit(70.0),base_dollar_year=pl.lit(2026),
        validation_status=pl.lit("approved"),source_version=pl.lit("upstream_valued_fixture"),
        discount_status=pl.lit("undiscounted"),cost_scope=pl.lit(HOUSING_SCOPE),
    )
    assert attach_loss_of_use(annual,costs,base_dollar_year=2026)["downtime_real"].to_list()==[70.0]*6


@pytest.mark.parametrize("case",["mismatched_year","already_valued"])
def test_input_identity_and_valuation_path_are_explicit(inputs,case):
    _,_,days,assets,housing,basis=inputs
    if case=="mismatched_year":days=days.with_columns(year=pl.lit(2040))
    else:days=days.with_columns(downtime_real=pl.lit(100.0))
    with pytest.raises(ContractViolationError):
        build_loss_of_use_costs(days,assets,housing,basis)
