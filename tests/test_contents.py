import math
import polars as pl
import pytest

from cadence_lifecycle.contents import contents_event_losses
from cadence_lifecycle.contracts import ContractViolationError
from cadence_lifecycle.water import interior_event_losses
from test_water import events, parameters


def test_published_midpoint_and_bounds():
    # Independent numeric evaluation from thesis p42, checked visually against PDF.
    water=interior_event_losses(events(),parameters())
    for x, expected in [(0.0,0.0), (0.5,math.sin(0.5)**1.5/2+0.5**20), (1.0,1.0)]:
        result=contents_event_losses(water.with_columns(pl.lit(x).alias("contents_wetness")))
        assert result["contents_damage_ratio"][0] == pytest.approx(expected)
        assert result["contents_loss_real"][0] == pytest.approx(expected*2000)


def test_zero_water_and_monotonic_separate_values():
    losses=[]
    for rain in [0.0,10.0,20.0,30.0,40.0,1e6]:
        r=contents_event_losses(interior_event_losses(events(effective_rain_mm=rain),parameters()))
        assert 0 <= r["contents_loss_real"][0] <= 2000
        losses.append(r["contents_loss_real"][0])
    assert losses[0] == losses[1] == losses[2] == 0  # reservoirs above contents retain water
    assert losses == sorted(losses)
    assert losses[-1] == 2000


def test_missing_contents_value_is_an_error():
    water=interior_event_losses(events(),parameters()).drop("contents_value_real")
    with pytest.raises(ContractViolationError):
        contents_event_losses(water)


def test_interior_published_midpoint_with_cap():
    result=interior_event_losses(events(effective_rain_mm=5.0),parameters())
    assert result["ceiling_damage_ratio"][0] == pytest.approx(0.5**5/2+0.6785*0.5)
