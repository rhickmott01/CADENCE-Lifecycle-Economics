import polars as pl
import pytest

from cadence_lifecycle.cashflows import KEYS, STREAMS, build_cashflows
from cadence_lifecycle.contracts import ContractViolationError
from cadence_lifecycle.pilot import pilot_metadata
from cadence_lifecycle.reporting import COMPONENTS, build_component_report, write_contribution_chart


@pytest.fixture
def inputs():
    options = pl.DataFrame({
        "asset_id": ["a", "a"], "decision_year": [2026, 2026],
        "option_id": ["baseline", "upgrade"], "material_id": ["asphalt", "metal"],
        "initial_rul_years": [2, 0], "new_eul_years": [2, 5],
        "replacement_cost_real": [100.0, 130.0], "roof_area_sqft": [100.0, 100.0],
        "existing_roof_basis_real": [100.0, 100.0], "existing_eul_years": [4, 4],
    })
    annual = options.select(KEYS).join(pl.DataFrame({"offset": range(3)}), how="cross")
    annual = annual.with_columns(*[pl.lit(0.0).alias(c) for c in STREAMS])
    return options, annual, pilot_metadata(options)


@pytest.mark.parametrize("rate", [0.0, 0.1, -0.1])
def test_components_match_independent_financial_example(inputs, rate):
    options, annual, metadata = inputs
    cash = build_cashflows(options, annual, 3, rate)
    report = build_component_report(cash, metadata, 2026)
    upgrade = report.filter(pl.col("option_id") == "upgrade")
    values = dict(zip(upgrade["component"], upgrade["npv_contribution_real"]))
    # Baseline pays 100 at t=2, credit 50 at t=3. Upgrade pays 130
    # at t=0, credit 52 at t=3. Attribution must preserve both credit signs.
    assert values["replacement"] == pytest.approx(100 / (1 + rate)**2 - 130)
    assert values["terminal_service_value"] == pytest.approx(2 / (1 + rate)**3)
    assert upgrade["npv_contribution_real"].sum() == pytest.approx(
        100 / (1 + rate)**2 - 130 + 2 / (1 + rate)**3
    )
    assert report.filter(pl.col("option_id") == "baseline")["npv_contribution_real"].abs().sum() == 0
    assert upgrade.height == len(COMPONENTS)
    assert upgrade.filter(pl.col("component") == "downtime")["status"][0] == "disabled"


def test_multiple_assets_and_decision_years_do_not_share_baselines(inputs):
    options, annual, _ = inputs
    options = pl.concat([options, options.with_columns(asset_id=pl.lit("b"), decision_year=pl.lit(2030, dtype=pl.Int64))])
    annual = pl.concat([annual, annual.with_columns(asset_id=pl.lit("b"), decision_year=pl.lit(2030, dtype=pl.Int64))])
    report = build_component_report(build_cashflows(options, annual, 3, 0.03), pilot_metadata(options), 2026)
    assert report.height == 4 * len(COMPONENTS)
    assert report.group_by(KEYS).agg(pl.col("baseline_pv_real").is_null().any())["baseline_pv_real"].any() is False


def test_maintenance_and_salvage_credit_are_separate_signed_components(inputs):
    options, annual, metadata = inputs
    annual = annual.with_columns(
        maintenance_real=pl.when(pl.col("option_id") == "baseline").then(10.0).otherwise(0.0),
        salvage_credit_real=pl.when(pl.col("option_id") == "upgrade").then(2.0).otherwise(0.0),
    )
    metadata = metadata.with_columns(enabled=pl.col("enabled") | pl.col("component").is_in(["maintenance", "salvage_credit"]))
    report = build_component_report(build_cashflows(options, annual, 3, 0), metadata, 2026)
    option = report.filter(pl.col("option_id") == "upgrade")
    values = dict(zip(option["component"], option["npv_contribution_real"]))
    assert values["maintenance"] == 30
    assert values["salvage_credit"] == 6
    assert option["npv_contribution_real"].sum() == 8  # original -28 + 30 + 6


@pytest.mark.parametrize("mutation,match", [
    ("missing_metadata", "exactly cover"), ("disabled_nonzero", "Disabled"),
    ("nan", "nonfinite"), ("null", "missing"),
    ("bad_factor", "reconcile"), ("bad_total", "reconcile"),
    ("duplicate", "duplicate"), ("no_baseline", "baseline"),
    ("missing_period", "support"), ("missing_terminal", "support"),
])
def test_report_rejects_incomplete_or_inconsistent_inputs(inputs, mutation, match):
    options, annual, metadata = inputs
    cash = build_cashflows(options, annual, 3, 0.03)
    if mutation == "missing_metadata":
        metadata = metadata.head(metadata.height - 1)
    elif mutation == "disabled_nonzero":
        metadata = metadata.with_columns(enabled=pl.lit(False))
    elif mutation in {"nan", "null"}:
        cash = cash.with_columns(disposal_real=pl.lit(float("nan") if mutation == "nan" else None, dtype=pl.Float64))
    elif mutation == "bad_factor":
        cash = cash.with_columns(discount_factor=pl.col("discount_factor") * 2)
    elif mutation == "bad_total":
        cash = cash.with_columns(total_real=pl.col("total_real") + 1)
    elif mutation == "duplicate":
        cash = pl.concat([cash, cash.head(1)])
    elif mutation == "no_baseline":
        cash = cash.filter(pl.col("option_id") != "baseline")
        metadata = metadata.filter(pl.col("option_id") != "baseline")
    elif mutation == "missing_period":
        cash = cash.filter(pl.col("offset") != 1)
    elif mutation == "missing_terminal":
        cash = cash.filter(pl.col("cashflow_type") != "terminal")
    with pytest.raises(ContractViolationError, match=match):
        build_component_report(cash, metadata, 2026)


def test_missing_annual_costs_are_not_silently_zeroed(inputs):
    options, annual, _ = inputs
    with pytest.raises(ContractViolationError, match="incomplete"):
        build_cashflows(options, annual.head(annual.height - 1), 3, 0.03)


def test_chart_is_byte_reproducible_and_explains_excluded_benefits(inputs, tmp_path):
    pytest.importorskip("matplotlib")
    options, annual, metadata = inputs
    report = build_component_report(build_cashflows(options, annual, 3, 0.03), metadata, 2026)
    first, second = tmp_path / "first.svg", tmp_path / "second.svg"
    subtitle = "Synthetic installation prices; casualty and hazard benefits excluded"
    write_contribution_chart(report, first, subtitle=subtitle)
    write_contribution_chart(report, second, subtitle=subtitle)
    assert first.read_bytes() == second.read_bytes()
    assert "Synthetic installation prices" in first.read_text()
    assert "casualty and hazard benefits excluded" in first.read_text()
