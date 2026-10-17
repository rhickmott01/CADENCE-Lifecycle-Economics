import polars as pl
from cadence_lifecycle.cashflows import build_cashflows, compare_options, STREAMS

def test_npv_and_baseline():
 options=pl.DataFrame({"asset_id":["a","a"],"option_id":["baseline","upgrade"],"decision_year":[2026,2026],"material_id":["asphalt","metal"],"initial_rul_years":[2,0],"new_eul_years":[2,5],"replacement_cost_real":[100.,130.],"roof_area_sqft":[100.,100.],"existing_roof_basis_real":[100.,100.],"existing_eul_years":[4,4]})
 annual=options.select("asset_id","decision_year","option_id").join(pl.DataFrame({"offset":[0,1,2]}),how="cross")
 for c in STREAMS:annual=annual.with_columns(pl.lit(0.).alias(c))
 cash=build_cashflows(options,annual,3,0)
 result=compare_options(cash)
 baseline=result.filter(pl.col("option_id")=="baseline")["incremental_npv_real"][0]
 assert baseline==0
 assert result.height==2
 # baseline 100 at year 2, terminal 50; upgrade 130 at 0, terminal 52
 assert result.filter(pl.col("option_id")=="baseline")["npc_real"][0]==50
 assert result.filter(pl.col("option_id")=="upgrade")["npc_real"][0]==78
