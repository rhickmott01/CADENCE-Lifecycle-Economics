import polars as pl
import pytest
from cadence_lifecycle.replacement import project_fixed_eul_events, terminal_residual
from cadence_lifecycle.contracts import ContractViolationError

def options():
 return pl.DataFrame({"asset_id":["a"],"option_id":["baseline"],"decision_year":[2026],"material_id":["asphalt_architectural"],"initial_rul_years":[8],"new_eul_years":[20],"replacement_cost_real":[20000.],"roof_area_sqft":[1500.],"existing_roof_basis_real":[12000.],"existing_eul_years":[20]})

def test_replacement_events():
 assert project_fixed_eul_events(options(),30)["event_year"].to_list()==[2034,2054]

def test_terminal_value():
 # Replaced in 2054, two years used by 2056 terminal; 18 years remain.
 assert terminal_residual(options(),30)["terminal_value_real"][0]==18000

def test_invalid_eul():
 with pytest.raises(ContractViolationError):project_fixed_eul_events(options().with_columns(pl.lit(0).alias("new_eul_years")))


def test_unreplaced_roof_uses_existing_basis_and_excludes_terminal_installation():
 roof=options().with_columns(initial_rul_years=pl.lit(35), existing_eul_years=pl.lit(40), replacement_cost_real=pl.lit(90000.0))
 assert project_fixed_eul_events(roof,30).is_empty()
 assert terminal_residual(roof,30)["terminal_value_real"][0]==1500.0
 boundary=roof.with_columns(initial_rul_years=pl.lit(30))
 assert project_fixed_eul_events(boundary,30).is_empty()
 assert terminal_residual(boundary,30)["terminal_value_real"][0]==0.0
