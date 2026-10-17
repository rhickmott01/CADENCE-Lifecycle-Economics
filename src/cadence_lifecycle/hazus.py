"""Preprocess existing age/IECC HAZUS consequence partitions with DuckDB."""
from pathlib import Path
import duckdb
from .contracts import ContractViolationError
from .consequences import MEASURES

def inspect_partition(partition: str):
    p=Path(partition)
    for n in ["curves_hu.parquet","curve_points_hu.parquet","curve_attributes_hu.parquet"]:
        if not (p/n).is_file():
            raise ContractViolationError(f"missing {p/n}")
    with duckdb.connect() as db:
        return {name:db.execute(f"DESCRIBE SELECT * FROM read_parquet(?)",[str(p/name)]).fetchall() for name in ["curves_hu.parquet","curve_points_hu.parquet","curve_attributes_hu.parquet"]}

def export_partition(partition:str, output_file:str):
    """Create compact long-form consequence lookup. Attribute rows retained separately.

    Never guesses terrain attribute names; retain original key/value table for
    exact archetype selection by a source-approved mapping in the caller.
    Output path must not already exist (immutable reference contract).
    """
    p=Path(partition);out=Path(output_file)
    if out.exists():
        raise ContractViolationError("immutable output already exists")
    inspect_partition(partition)
    out.parent.mkdir(parents=True,exist_ok=True)
    measures=tuple(MEASURES)
    with duckdb.connect() as db:
        c=str(p/'curves_hu.parquet'); pts=str(p/'curve_points_hu.parquet')
        sql="""SELECT c.*, p.x AS wind_speed_mph, p.y AS response_value
                 FROM read_parquet(?) c JOIN read_parquet(?) p USING (curve_id)
                 WHERE c.damage_type IN (?,?,?,?,?)"""
        db.execute("CREATE TEMP TABLE selected AS "+sql,[c,pts,*measures])
        dup=db.execute("SELECT count(*) FROM (SELECT curve_id,wind_speed_mph,count(*) n FROM selected GROUP BY 1,2 HAVING n>1)").fetchone()[0]
        if dup: raise ContractViolationError("duplicate curve/wind-speed points")
        db.execute("COPY selected TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",[str(out)])
    return out
