"""Preprocess existing age/IECC HAZUS consequence partitions with DuckDB."""
from pathlib import Path
import duckdb
from .contracts import ContractViolationError
from .consequences import MEASURES

def inspect_loss_of_use_partition(partition: str) -> dict:
    """Audit one explicitly selected partition without deriving annual risk.

    Counts and checksums describe source bytes; they do not approve a material
    proxy, confirm residential displacement semantics, or select hazard tails.
    """
    import hashlib
    import pyarrow.parquet as pq

    schemas=inspect_partition(partition)
    p=Path(partition).resolve()
    files={}
    for name in schemas:
        path=p/name
        digest=hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda:source.read(1024*1024),b""):
                digest.update(chunk)
        parquet=pq.ParquetFile(path)
        files[name]={"sha256":digest.hexdigest(),"size_bytes":path.stat().st_size,
                     "rows":parquet.metadata.num_rows,"row_groups":parquet.num_row_groups,
                     "schema":str(parquet.schema_arrow)}
    with duckdb.connect() as db:
        for alias,name in [("curves","curves_hu.parquet"),("points","curve_points_hu.parquet"),("attrs","curve_attributes_hu.parquet")]:
            db.read_parquet(str(p/name)).create_view(alias)
        db.sql("CREATE VIEW selected AS SELECT * FROM curves WHERE damage_type='loss_of_use'")
        count=db.sql("SELECT count(*) FROM selected").fetchone()[0]
        if not count:
            raise ContractViolationError("No loss-of-use curves in the selected partition")
        if db.sql("SELECT count(*)-count(DISTINCT curve_id) FROM selected").fetchone()[0]:
            raise ContractViolationError("Duplicate or missing loss-of-use curve IDs")
        invalid=db.sql("""SELECT count(*) FROM selected c LEFT JOIN points p USING(curve_id)
            WHERE p.x IS NULL OR p.y IS NULL OR NOT isfinite(p.x) OR NOT isfinite(p.y)
            OR p.x<0 OR p.y<0""").fetchone()[0]
        duplicates=db.sql("""SELECT count(*) FROM (SELECT curve_id,x,count(*) n FROM selected
            JOIN points USING(curve_id) GROUP BY 1,2 HAVING n<>1)""").fetchone()[0]
        short=db.sql("""SELECT count(*) FROM (SELECT c.curve_id,count(p.x) n FROM selected c
            LEFT JOIN points p USING(curve_id) GROUP BY 1 HAVING n<2)""").fetchone()[0]
        if invalid or duplicates or short:
            raise ContractViolationError("Loss-of-use point support is missing, duplicate, negative or nonfinite")
        support=db.sql("""SELECT min(x),max(x),min(y),max(y),count(*) FROM selected
            JOIN points USING(curve_id)""").fetchone()
        grid=db.sql("""SELECT min(n),max(n) FROM (SELECT curve_id,count(*) n FROM selected
            JOIN points USING(curve_id) GROUP BY 1)""").fetchone()
        buildings=dict(db.sql("SELECT building_type,count(*) FROM selected GROUP BY 1 ORDER BY 1").fetchall())
        source_columns=["hazus_version","source_agency","source_file","source_table","transformation_version","climate_region","asset_age"]
        source_rows=db.sql("SELECT DISTINCT "+",".join(source_columns)+" FROM selected ORDER BY "+",".join(source_columns)).fetchall()
        attribute_keys=[r[0] for r in db.sql("SELECT DISTINCT key FROM attrs JOIN selected USING(curve_id) ORDER BY key").fetchall()]
        occupancy_nulls=db.sql("SELECT count(*) FROM selected WHERE occupancy IS NULL").fetchone()[0]
    return {
        "partition":str(p),"files":files,"loss_of_use_curve_count":count,
        "building_type_counts":buildings,"wind_speed_mph_min":support[0],"wind_speed_mph_max":support[1],
        "response_min":support[2],"response_max":support[3],"point_count":support[4],
        "points_per_curve_min":grid[0],"points_per_curve_max":grid[1],
        "source_records":[dict(zip(source_columns,row)) for row in source_rows],
        "attribute_keys":attribute_keys,"occupancy_null_count":occupancy_nulls,
        "status":"source_structure_checked; annual_risk_not_computed",
        "unit_status":"No explicit response unit field in current schema; source definition needs verification",
        "remaining_requirements":["residential displacement interpretation and roof mapping approval",
                                  "asset climate zone and terrain", "annual hazard inputs and integration/tail policy",
                                  "long-duration allocation to financial years", "documented housing dollar-year conversion"],
    }

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
