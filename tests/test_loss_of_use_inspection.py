import hashlib

import polars as pl
import pytest

from cadence_lifecycle.contracts import ContractViolationError
from cadence_lifecycle.hazus import inspect_loss_of_use_partition


@pytest.fixture
def partition(tmp_path):
    pl.DataFrame({
        "curve_id":["loss","building"],"damage_type":["loss_of_use","building_loss"],
        "building_type":["WSF1","WSF1"],"occupancy":[None,None],
        "hazus_version":["test"]*2,"source_agency":["synthetic fixture"]*2,
        "source_file":["fixture.xlsx"]*2,"source_table":["fixture"]*2,
        "transformation_version":["test"]*2,"climate_region":["1A"]*2,"asset_age":[1,1],
    },schema_overrides={"occupancy":pl.Int32}).write_parquet(tmp_path/"curves_hu.parquet")
    pl.DataFrame({"curve_id":["loss"]*3+["building"],"x":[50.0,100.0,250.0,100.0],
                  "y":[0.0,20.0,720.0,0.5]}).write_parquet(tmp_path/"curve_points_hu.parquet")
    pl.DataFrame({"curve_id":["loss"],"key":["terrain_id"],"value":["1"]}).write_parquet(tmp_path/"curve_attributes_hu.parquet")
    return tmp_path


def test_inspection_preserves_raw_response_and_source_files(partition):
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in partition.iterdir()}
    result=inspect_loss_of_use_partition(str(partition))
    assert result["loss_of_use_curve_count"]==1
    assert result["point_count"]==3
    assert result["response_max"]==720
    assert result["wind_speed_mph_min"]==50
    assert result["building_type_counts"]=={"WSF1":1}
    assert result["occupancy_null_count"]==1
    assert "annual_risk_not_computed" in result["status"]
    assert "needs verification" in result["unit_status"]
    after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in partition.iterdir()}
    assert before==after
    assert {name:item["sha256"] for name,item in result["files"].items()}==before


@pytest.mark.parametrize("case",["duplicate","negative","nonfinite","missing_points","no_loss_curves"])
def test_source_support_errors_are_rejected(partition,case):
    path=partition/"curve_points_hu.parquet"
    points=pl.read_parquet(path)
    if case=="duplicate":points=pl.concat([points,points.head(1)])
    elif case=="negative":points=points.with_columns(y=pl.lit(-1.0))
    elif case=="nonfinite":points=points.with_columns(y=pl.lit(float("nan")))
    elif case=="missing_points":points=points.filter(pl.col("curve_id")!="loss")
    else:
        curves=partition/"curves_hu.parquet"
        pl.read_parquet(curves).with_columns(damage_type=pl.lit("building_loss")).write_parquet(curves)
    points.write_parquet(path)
    with pytest.raises(ContractViolationError):
        inspect_loss_of_use_partition(str(partition))
