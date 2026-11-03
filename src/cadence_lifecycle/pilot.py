"""Reproducible illustrative report over existing lifecycle calculation APIs."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import tempfile

import polars as pl

from .cashflows import KEYS, STREAMS, build_cashflows, compare_options
from .contracts import ContractViolationError
from .disposal import attach_disposal, build_disposal_events, read_source_mass
from .io import write_run
from .reference import select_housing_rate
from .reporting import COMPONENTS, build_component_report, write_contribution_chart

ROOT = Path(__file__).resolve().parents[2]


def pilot_options() -> pl.DataFrame:
    """Original pilot financial/EUL assumptions, with exact source subtype IDs."""
    return pl.DataFrame({
        "asset_id": ["house_001"] * 3, "decision_year": [2026] * 3,
        "option_id": ["baseline", "replace_asphalt_now", "upgrade_metal_now"],
        "material_id": ["Architectural Asphalt Shingles", "Architectural Asphalt Shingles", "Metal Roofing"],
        "existing_material_id": ["Architectural Asphalt Shingles"] * 3,
        "initial_rul_years": [8, 0, 0], "new_eul_years": [20, 20, 40],
        "replacement_cost_real": [12000.0, 12000.0, 25000.0],
        "roof_area_sqft": [2000.0] * 3, "existing_roof_basis_real": [12000.0] * 3,
        "existing_eul_years": [20] * 3, "state_code": ["NC"] * 3,
        "county_fips": ["37063"] * 3,
    })


def pilot_metadata(options: pl.DataFrame) -> pl.DataFrame:
    rows = []
    details = {
        "disposal": (True, "EREF_2024+shared_roof_mass+CADENCE_disposal_helper", 2024,
                     "fixed_2026_real_proxy; source rate held constant without inflation conversion"),
        "replacement": (True, "synthetic_pilot_installation_costs", 2026,
                        "combined_installation_cost; fixed_EUL_pilot_override"),
        "terminal_service_value": (True, "lifecycle_terminal_residual", 2026,
                                   "straight_line_remaining_service; synthetic_eligible_basis"),
    }
    for key in options.select(KEYS).iter_rows(named=True):
        for component in COMPONENTS:
            enabled, source, year, method = details.get(
                component, (False, "disabled_by_pilot", None, "no_supported_input; explicitly_excluded")
            )
            rows.append({**key, "component": component, "enabled": enabled,
                         "source": source, "source_year": year, "valuation_method": method})
    return pl.DataFrame(rows)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_cost_driver_pilot(shared_root: Path, cadence_root: Path, output_root: Path) -> Path:
    """Publish a new write-once run only within this repository."""
    output_root = Path(output_root).resolve()
    if not output_root.is_relative_to(ROOT):
        raise ContractViolationError("Pilot outputs must stay inside CADENCE-Lifecycle-Economics")
    shared_root, cadence_root = Path(shared_root).resolve(), Path(cadence_root).resolve()
    sources = {
        "eref_2024": shared_root / "disposal/EREF_2024_Tipping_Fees_Parsed.csv",
        "roof_mass": shared_root / "material_mass/roofing_lbs.csv",
        "hud_2025": shared_root / "loss_of_use/temporary_housing_relocation_costs.csv",
        **{f"cadence_{name}": cadence_root / f"src/cadence/economics/{name}.py"
           for name in ("contracts", "materials", "externalities")},
    }
    for path in sources.values():
        if not path.is_file():
            raise ContractViolationError(f"Missing reference/source: {path}")
    identities = {name: _sha(path) for name, path in sources.items()}
    # Capture working source, since a dirty HEAD does not identify executable code.
    for path in sorted((ROOT / "src/cadence_lifecycle").glob("*.py")):
        identities[str(path.relative_to(ROOT))] = _sha(path)
    identities["pyproject.toml"] = _sha(ROOT / "pyproject.toml")
    options = pilot_options()
    metadata = pilot_metadata(options)
    identities["options"] = hashlib.sha256(options.write_json().encode()).hexdigest()
    identities["component_metadata"] = hashlib.sha256(metadata.write_json().encode()).hexdigest()
    config = {
        "report_schema_version": "cost_driver_v1", "horizon_years": 30,
        "real_discount_rate": 0.03, "base_dollar_year": 2026,
        "discount_timing": "offset_t; terminal_at_30", "baseline_option_id": "baseline",
        "price_status": "synthetic_installation_costs", "eul_status": "illustrative_fixed_EUL_overrides",
        "disposal_dollar_basis": "fixed_2026_real_proxy; no_inflation_conversion",
        "mass_identity": "exact_source_subtypes; not_official_class_consolidation",
        "casualty_status": "research_pending; excluded_from_decision_total",
        "housing_status": "reference_rate_only; no_supported_expected_downtime_input",
        "disabled_components": [c for c in COMPONENTS if c not in
                                {"replacement", "disposal", "terminal_service_value"}],
        "versions": {name: importlib.metadata.version(name) for name in
                     ("polars", "pyarrow", "pydantic", "matplotlib", "numpy")},
    }
    annual = options.select(KEYS).join(pl.DataFrame({"offset": range(30)}), how="cross")
    annual = annual.with_columns(*[pl.lit(0.0).alias(c) for c in STREAMS])
    mass = read_source_mass(sources["roof_mass"])
    events = build_disposal_events(options, mass, sources["eref_2024"], cadence_root, 30)
    annual = attach_disposal(annual, events)
    cashflows = build_cashflows(options, annual, 30, 0.03)
    contributions = build_component_report(cashflows, metadata, 2026)
    results = compare_options(cashflows).join(
        contributions.group_by(KEYS).agg(pl.col("npv_contribution_real").sum().alias("contribution_sum_real")),
        on=KEYS, validate="1:1",
    ).with_columns(
        (pl.col("contribution_sum_real") - pl.col("incremental_npv_real")).alias("reconciliation_error_real")
    ).sort(KEYS)
    housing = select_housing_rate(sources["hud_2025"], "37063", 2025)
    # Render first so missing plotting dependencies do not publish a partial run.
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_root) as staging:
        chart = Path(staging) / "npv_contributions.svg"
        preview = chart.with_suffix(".png")
        write_contribution_chart(
            contributions, chart, preview_path=preview,
            subtitle="Synthetic installation prices; fixed-EUL pilot; casualty and hazard benefits excluded",
        )
        target = write_run(str(Path(staging) / "runs"), config, identities, {
            "options": options, "annual_costs": annual.sort(KEYS + ["offset"]),
            "disposal_events": events, "annual_cashflows": cashflows,
            "component_metadata": metadata, "npv_contributions": contributions,
            "option_results": results, "housing_reference": housing,
            "mass_reference": mass,
        })
        (target / chart.name).write_bytes(chart.read_bytes())
        (target / preview.name).write_bytes(preview.read_bytes())
        contributions.write_csv(target / "npv_contributions.csv")
        events.write_csv(target / "disposal_events.csv")
        results.write_csv(target / "option_results.csv")
        provenance = {
            "sources": {name: {"path": str(path), "sha256": identities[name]} for name, path in sources.items()},
            "artifacts": {p.name: _sha(p) for p in sorted(target.iterdir()) if p.is_file()},
            "cadence_head": subprocess.check_output(["git", "-C", str(cadence_root), "rev-parse", "HEAD"], text=True).strip(),
            "lifecycle_head": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
            "working_tree_identity": "per_source_hashes_in_run_metadata; HEAD_is_context_only",
            "reproduce": ".venv/bin/python -B scripts/run_cost_driver_analysis.py --output-root outputs/cost_driver_reproduction",
        }
        (target / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
        if any(_sha(path) != identities[name] for name, path in sources.items()):
            raise ContractViolationError("Reference/source changed during run; refusing publication")
        published = output_root / "schema_version=v0.1" / target.name
        published.parent.mkdir(parents=True, exist_ok=True)
        if published.exists():
            raise ContractViolationError(f"write-once run already exists: {published}")
        target.rename(published)
    return published


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared-root", type=Path, default=ROOT.parent / "cadence_shared_data/reference_data")
    parser.add_argument("--cadence-root", type=Path, default=ROOT.parent / "CADENCE")
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs/cost_driver_analysis")
    args = parser.parse_args()
    target = run_cost_driver_pilot(args.shared_root, args.cadence_root, args.output_root)
    print(f"Reconciled contribution table and chart: {target}")
    print(pl.read_csv(target / "option_results.csv"))


if __name__ == "__main__":
    main()
