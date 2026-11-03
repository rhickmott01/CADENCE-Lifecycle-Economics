import polars as pl
import pytest

from cadence_lifecycle.contracts import ContractViolationError
from cadence_lifecycle.reference import select_housing_rate


def test_housing_selection_preserves_fips_and_accepts_only_identical_duplicates(tmp_path):
    rows = pl.DataFrame({"county_fips": ["01001", "01001", "01001"], "year": [2025, 2025, 2024],
                         "primary_bedroom": ["Two-Bedroom"] * 3, "relocation_cost_per_day": [50.0, 50.0, 40.0]})
    path = tmp_path / "housing.csv"
    rows.write_csv(path)
    rate = select_housing_rate(path, "01001", 2025)
    assert rate["county_fips"][0] == "01001"
    assert rate["observation_count"][0] == 2
    assert rate["relocation_cost_per_day"][0] == 50
    rows.with_columns(relocation_cost_per_day=pl.Series([50.0, 55.0, 40.0])).write_csv(path)
    with pytest.raises(ContractViolationError, match="Ambiguous"):
        select_housing_rate(path, "01001", 2025)


def test_housing_missing_or_invalid_county_is_not_zero(tmp_path):
    path = tmp_path / "housing.csv"
    pl.DataFrame({"county_fips": ["01001"], "year": [2025], "primary_bedroom": ["Two-Bedroom"],
                  "relocation_cost_per_day": [50.0]}).write_csv(path)
    with pytest.raises(ContractViolationError, match="No housing rate"):
        select_housing_rate(path, "01003", 2025)
    with pytest.raises(ContractViolationError, match="five-character"):
        select_housing_rate(path, "1001", 2025)
