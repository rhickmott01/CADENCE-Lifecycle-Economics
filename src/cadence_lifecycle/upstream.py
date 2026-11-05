"""Opt-in read-only bridge to unmodified CADENCE source calculations.

The child loads only contracts/materials/externalities, avoiding CADENCE's eager
package initializers (which pull in plotting and geospatial pipelines). No source
is copied or rewritten. Bytecode writes are disabled. Private API use is explicit
and upstream source hashes must accompany published runs.
"""

import json
from pathlib import Path
import subprocess
import sys

import polars as pl

def _call(cadence_root: Path, operation: str, **payload) -> pl.DataFrame:
    from .contracts import ContractViolationError
    root = Path(cadence_root).resolve()
    for name in ("contracts", "materials", "externalities"):
        path = root / "src/cadence/economics" / f"{name}.py"
        if not path.is_file():
            raise ContractViolationError(f"Missing CADENCE source: {path}")
    result = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).resolve()), str(root), operation],
        input=json.dumps(payload, allow_nan=False), text=True, capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ContractViolationError(f"CADENCE {operation} failed: {result.stderr.strip()}")
    return pl.read_json(result.stdout.encode())


def price_disposal(cadence_root: Path, base: pl.DataFrame, fees_path: Path) -> pl.DataFrame:
    """Delegate fee fallback and short-ton pricing to CADENCE's existing helper."""
    return _call(cadence_root, "disposal", rows=base.to_dicts(), fees=str(Path(fees_path).resolve()))


def evaluate_upstream_economics(cadence_root: Path, state: pl.DataFrame, damage: pl.DataFrame,
                                costs: pl.DataFrame, config: dict) -> pl.DataFrame:
    """Read-only source reconciliation helper; no state or hazard simulation."""
    return _call(cadence_root,"annual_economics",state=state.to_dicts(),damage=damage.to_dicts(),
                 costs=costs.to_dicts(),config=config)


def load_material_mass(cadence_root: Path, mass_path: Path,
                       mapping_path: Path, class_map_path: Path) -> pl.DataFrame:
    """Use CADENCE's approved official-class mapper when its inputs are available."""
    from .contracts import ContractViolationError
    paths = [Path(p).resolve() for p in (mass_path, mapping_path, class_map_path)]
    for path in paths:
        if not path.is_file():
            raise ContractViolationError(f"Required approved mapping/reference absent: {path}")
    return _call(cadence_root, "material_mass", paths=[str(p) for p in paths]).with_columns(
        pl.col("official_material_id").alias("material_id"),
        pl.lit("approved_cadence_lookup").alias("mass_mapping_method"),
    )


def _main():
    import importlib.util
    import types

    root, operation = Path(sys.argv[1]), sys.argv[2]
    # Fresh process: isolate source loading from CADENCE's eager __init__ imports.
    for package in ("cadence", "cadence.economics"):
        module = types.ModuleType(package)
        module.__path__ = [str(root / "src" / package.replace(".", "/"))]
        sys.modules[package] = module
    loaded = {}
    for name in ("contracts", "materials", "externalities"):
        qualified = f"cadence.economics.{name}"
        spec = importlib.util.spec_from_file_location(
            qualified, root / "src/cadence/economics" / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        spec.loader.exec_module(module)
        loaded[name] = module
    payload = json.load(sys.stdin)
    if operation == "disposal":
        result = loaded["externalities"]._attach_disposal_cost(
            pl.DataFrame(payload["rows"]), Path(payload["fees"])
        )
    elif operation == "material_mass":
        result = loaded["materials"].build_material_mass_lookup(
            *(Path(p) for p in payload["paths"])
        )
    elif operation == "annual_economics":
        from cadence.economics.alternative_analysis import build_annual_alternative_economics
        result=build_annual_alternative_economics(pl.DataFrame(payload["state"]),pl.DataFrame(payload["damage"]),
            pl.DataFrame(payload["costs"]),loaded["contracts"].EconomicsRunConfig.model_validate(payload["config"]))
    else:
        raise ValueError(f"Unknown bridge operation: {operation}")
    print(result.write_json())


if __name__ == "__main__":
    _main()
