import polars as pl
import pytest

from cadence_lifecycle.cadence_exchange import adapt_cadence_analysis
from cadence_lifecycle.contracts import ContractViolationError
from test_analysis import inputs


def upstream_fixture(inputs):
    options,annual,_,config,_,_=inputs
    annual=annual.join(options.select('asset_id','option_id','scenario_id'),on=['asset_id','option_id'],validate='m:1')
    upstream=annual.with_columns((pl.col('decision_year')+pl.col('offset')).alias('year'),
        pl.lit('real_2024_usd').alias('dollar_basis'),pl.lit('OFFICIAL_METAL').alias('scenario_material_id'),
        pl.lit('OFFICIAL_ASPHALT').alias('removed_material_id'),(pl.col('offset')==0).alias('installation_event'),
        pl.lit(1000.).alias('roof_area_sqft'),pl.lit(0.).alias('annual_repair_cost_usd'),
        pl.when(pl.col('offset')==0).then(100.).otherwise(0.).alias('installation_event_capex_usd'),
        pl.lit(0.).alias('enabled_event_disposal_cost_usd'),pl.lit(0.).alias('enabled_event_carbon_cost_usd'))
    return upstream,upstream


def test_source_costs_events_and_physical_scenario_ids_are_preserved(inputs):
    upstream,supplements=upstream_fixture(inputs)
    r=adapt_cadence_analysis(upstream,supplements,inputs[3],decision_year=2026,source_version='CADENCE_fixture',terminal_policy='none')
    assert r['options']['option_id'].to_list()==r['options']['scenario_id'].to_list()
    assert r['replacement_events']['event_cost_real'].to_list()==[100.,100.]
    assert r['terminal_values']['terminal_value_real'].sum()==0
    assert r['annual_costs']['maintenance_real'].sum()==300


@pytest.mark.parametrize('case',['wrong_basis','carbon','partial_history','non_event_cost'])
def test_adapter_rejects_incompatible_upstream_values(inputs,case):
    upstream,supplements=upstream_fixture(inputs)
    if case=='wrong_basis':upstream=upstream.with_columns(dollar_basis=pl.lit('real_2026_usd'))
    elif case=='carbon':upstream=upstream.with_columns(enabled_event_carbon_cost_usd=pl.lit(10.))
    elif case=='partial_history':upstream=upstream.with_columns(repair_cost_incomplete=pl.lit(True))
    else:upstream=upstream.with_columns(installation_event=pl.lit(False))
    with pytest.raises(ContractViolationError):
        adapt_cadence_analysis(upstream,supplements,inputs[3],decision_year=2026,source_version='fixture',terminal_policy='none')
