import hashlib
import json
from pathlib import Path
import tempfile

import polars as pl
import pytest

from cadence_lifecycle.contracts import ContractViolationError
from cadence_lifecycle.pilot import ROOT, run_cost_driver_pilot


def test_full_pilot_is_reproducible_reconciled_and_write_once():
    pytest.importorskip("matplotlib")
    shared = ROOT.parent / "cadence_shared_data/reference_data"
    cadence = ROOT.parent / "CADENCE"
    if not shared.exists() or not (cadence / "src/cadence/economics/externalities.py").exists():
        pytest.skip("Read-only sibling references unavailable")
    # Keep even temporary generated artifacts inside the authorized repository.
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        directory = Path(directory)
        first = run_cost_driver_pilot(shared, cadence, directory / "first")
        second = run_cost_driver_pilot(shared, cadence, directory / "second")
        assert first.name == second.name
        assert sorted(p.name for p in first.iterdir()) == sorted(p.name for p in second.iterdir())
        for path in first.iterdir():
            assert path.read_bytes() == (second / path.name).read_bytes(), path.name
        report = pl.read_csv(first / "npv_contributions.csv")
        assert report.height == 30  # 10 components across 3 scenarios
        disposal = report.filter(pl.col("component") == "disposal")
        values = dict(zip(disposal["option_id"], disposal["npv_contribution_real"]))
        assert values["replace_asphalt_now"] == pytest.approx(-32.48176408933844)
        assert values["upgrade_metal_now"] == pytest.approx(22.484396407509905)
        results = pl.read_csv(first / "option_results.csv")
        assert results["reconciliation_error_real"].abs().max() < 1e-8
        housing = pl.read_parquet(first / "housing_reference.parquet")
        assert housing["county_fips"][0] == "37063"
        assert housing["relocation_cost_per_day"][0] == 62.4
        manifest = json.loads((first / "provenance.json").read_text())
        for name, expected in manifest["artifacts"].items():
            assert hashlib.sha256((first / name).read_bytes()).hexdigest() == expected
        with pytest.raises(ContractViolationError, match="write-once"):
            run_cost_driver_pilot(shared, cadence, directory / "first")


def test_pilot_rejects_output_outside_repository(tmp_path):
    with pytest.raises(ContractViolationError, match="inside"):
        run_cost_driver_pilot(Path("unused"), Path("unused"), tmp_path)
