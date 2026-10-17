"""Write-once Parquet outputs with deterministic run manifests."""
import hashlib, json
from pathlib import Path
import polars as pl
from .contracts import ContractViolationError

def write_run(run_root:str, config:dict, inputs:dict[str,str], tables:dict[str,pl.DataFrame]):
    payload=json.dumps({"config":config,"inputs":inputs,"package_version":"0.1.0"},sort_keys=True)
    run_id=hashlib.sha256(payload.encode()).hexdigest()[:24]
    target=Path(run_root)/f"schema_version=v0.1"/f"run_id={run_id}"
    if target.exists():
        raise ContractViolationError(f"write-once run already exists: {target}")
    target.mkdir(parents=True)
    try:
        for name,frame in tables.items():
            if not name.replace("_","").isalnum():
                raise ContractViolationError("invalid output table name")
            frame.write_parquet(target/f"{name}.parquet",compression="zstd")
        (target/"run_metadata.json").write_text(json.dumps({"run_id":run_id,"config":config,"inputs":inputs,"package_version":"0.1.0"},indent=2,sort_keys=True))
    except Exception:
        import shutil
        shutil.rmtree(target)
        raise
    return target
