import polars as pl
import pytest

from cadence_lifecycle.contracts import ContractViolationError
from cadence_lifecycle.water import WaterParameters, interior_event_losses


def parameters(**changes):
    return WaterParameters(**(dict(parameter_set_id="synthetic", source_reference="test fixture",
        covering_leakage_fraction=0.1, entry_efficiency=1.0,
        ceiling_capacity_l_per_m2=1.0, partitions_capacity_l_per_m2=1.0, contents_capacity_l_per_m2=2.0,
        floor_capacity_l_per_m2=1.0) | changes))


def events(**changes):
    row = dict(asset_id="a", decision_year=2024, option_id="baseline", offset=0, event_id="storm",
        roof_area_m2=100.0, wetted_area_m2=10.0, effective_rain_mm=10.0,
        deck_breach_fraction=0.01, cover_loss_fraction=0.0, ceiling_value_real=1000.0,
        partitions_value_real=1000.0, floor_value_real=1000.0,
        cabinets_value_real=0.0, electrical_value_real=0.0, contents_value_real=2000.0, base_dollar_year=2024, source_version="synthetic")
    return pl.DataFrame([row | changes])


def test_independent_water_volume_and_ceiling_only_case():
    # One m² opening receiving 10 mm = 10 liters; ceiling holds all 10 liters.
    r = interior_event_losses(events(), parameters()).row(0, named=True)
    assert r["water_entry_l"] == 10
    assert r["ceiling_retained_l"] == 10
    assert r["ceiling_overflow_l"] == 0
    assert r["interior_loss_real"] == 1000


@pytest.mark.parametrize("changes", [dict(effective_rain_mm=0.0),
    dict(deck_breach_fraction=0.0, cover_loss_fraction=0.0)])
def test_zero_water_zero_interior(changes):
    r = interior_event_losses(events(**changes), parameters())
    assert r["water_entry_l"][0] == r["interior_loss_real"][0] == 0


def test_monotonic_bounded_and_mass_conserved():
    losses=[]
    for rain in [0.0, 1.0, 10.0, 100.0, 1e6]:
        r=interior_event_losses(events(effective_rain_mm=rain), parameters()).row(0,named=True)
        assert sum(r[f"{c}_retained_l"] for c in ["ceiling","partitions","contents","floor"])+r["ponded_water_l"] == pytest.approx(r["water_entry_l"])
        assert 0 <= r["interior_loss_real"] <= 3000
        losses.append(r["interior_loss_real"])
    assert losses == sorted(losses)


def test_cover_and_deck_paths_do_not_overlap():
    r=interior_event_losses(events(deck_breach_fraction=1.0, cover_loss_fraction=1.0), parameters())
    assert r["effective_opening_m2"][0] == 100


@pytest.mark.parametrize("changes", [dict(effective_rain_mm=float("nan")),
    dict(wetted_area_m2=0.0), dict(deck_breach_fraction=1.01),
    dict(ceiling_value_real=None), dict(source_version=""), dict(offset=0.5)])
def test_bad_or_missing_input_rejected(changes):
    with pytest.raises(ContractViolationError):
        interior_event_losses(events(**changes),parameters())
