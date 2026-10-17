import polars as pl
import pytest
from cadence_lifecycle.consequences import integrate_discrete_hazard, monetize_consequences
from cadence_lifecycle.contracts import ContractViolationError

def test_discrete_expectation():
 curves=pl.DataFrame({"asset_id":["a","a"],"year":[2026,2026],"option_id":["base","base"],"damage_type":["building_loss","building_loss"],"wind_speed_mph":[100.,150.],"response_value":[.1,.3]})
 hazard=pl.DataFrame({"asset_id":["a","a"],"year":[2026,2026],"wind_speed_mph":[100.,150.],"probability_mass":[.75,.25]})
 result=integrate_discrete_hazard(curves,hazard)
 assert result["expected_response"][0]==pytest.approx(.15)
 exposure=pl.DataFrame({"asset_id":["a"],"year":[2026],"option_id":["base"],"building_value_real":[100000.],"contents_value_real":[20000.],"daily_relocation_real":[100.],"debris_area_sqft":[1000.],"debris_cleanup_per_ton_real":[200.]})
 assert monetize_consequences(result,exposure)["cost_real"][0]==pytest.approx(15000)

def test_invalid_hazard_mass():
 c=pl.DataFrame({"asset_id":["a"],"year":[2026],"option_id":["x"],"damage_type":["loss_of_use"],"wind_speed_mph":[100.],"response_value":[2.]})
 h=pl.DataFrame({"asset_id":["a"],"year":[2026],"wind_speed_mph":[100.],"probability_mass":[.8]})
 with pytest.raises(ContractViolationError):integrate_discrete_hazard(c,h)
