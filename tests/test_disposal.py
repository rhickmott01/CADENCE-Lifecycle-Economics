from pathlib import Path

import polars as pl
import pytest

from cadence_lifecycle.cashflows import KEYS
from cadence_lifecycle.contracts import ContractViolationError
from cadence_lifecycle.disposal import attach_disposal, build_disposal_events, read_source_mass
from cadence_lifecycle.pilot import pilot_options
from cadence_lifecycle.upstream import load_material_mass

ROOT = Path(__file__).resolve().parents[1]
CADENCE = ROOT.parent / "CADENCE"
SHARED = ROOT.parent / "cadence_shared_data/reference_data"


@pytest.fixture
def references():
    if not (CADENCE / "src/cadence/economics/externalities.py").exists() or not SHARED.exists():
        pytest.skip("Read-only sibling references unavailable")
    return read_source_mass(SHARED / "material_mass/roofing_lbs.csv"), SHARED / "disposal/EREF_2024_Tipping_Fees_Parsed.csv"


def test_generated_events_track_actual_removed_material_and_terminal_boundary(references):
    mass, fees = references
    options = pilot_options().filter(pl.col("option_id") == "upgrade_metal_now").with_columns(new_eul_years=pl.lit(10))
    events = build_disposal_events(options, mass, fees, CADENCE, 20)
    assert events["event_year"].to_list() == [2026, 2036]  # 2046 excluded
    assert events["removed_material_id"].to_list() == ["Architectural Asphalt Shingles", "Metal Roofing"]
    assert events["removed_roof_mass_lbs"].to_list() == [5000, 2200]
    assert events["disposal_real"].to_list() == pytest.approx([99.275, 43.681])
    assert events["disposal_fee_usd_per_short_ton"].to_list() == [39.71, 39.71]
    assert events["disposal_geography_level"].to_list() == ["state", "state"]
    assert events["source_reference"].to_list() == [
        "Owens Corning / CertainTeed Technical Data Sheets", "Metal Roofing Alliance (MRA)",
    ]
    assert events["typical_service_life_years"].to_list() == [27.5, 55.0]


def test_delayed_first_replacement_still_removes_existing_roof(references):
    mass, fees = references
    options = pilot_options().filter(pl.col("option_id") == "upgrade_metal_now").with_columns(
        initial_rul_years=pl.lit(2), new_eul_years=pl.lit(10)
    )
    events = build_disposal_events(options, mass, fees, CADENCE, 20)
    assert events["offset"].to_list() == [2, 12]
    assert events["removed_material_id"].to_list() == ["Architectural Asphalt Shingles", "Metal Roofing"]


@pytest.mark.parametrize("tier", ["region", "national"])
def test_uses_upstream_geographic_fallback(references, tmp_path, tier):
    mass, fees = references
    frame = pl.read_csv(fees).filter(pl.col("Region/State") != "North Carolina")
    # The actual Southeast reference rate is used below, not a duplicate crosswalk.
    if tier == "region":
        expected = frame.filter(pl.col("Region/State") == "Southeast")["Average tipping Fee"].item()
    else:
        frame = frame.filter(pl.col("Region/State") != "Southeast")
        expected = 62.28
    path = tmp_path / "fees.csv"
    frame.write_csv(path)
    result = build_disposal_events(pilot_options(), mass, path, CADENCE)
    assert result["disposal_geography_level"].unique().to_list() == [tier]
    assert result["disposal_fee_usd_per_short_ton"].unique().to_list() == [expected]


def test_no_events_means_zero_disposal_without_fabricated_event(references):
    mass, fees = references
    options = pilot_options().filter(pl.col("option_id") == "baseline").with_columns(initial_rul_years=pl.lit(30))
    events = build_disposal_events(options, mass, fees, CADENCE)
    assert events.is_empty()
    annual = options.select(KEYS).join(pl.DataFrame({"offset": range(30)}), how="cross").with_columns(disposal_real=pl.lit(0.0))
    assert attach_disposal(annual, events)["disposal_real"].sum() == 0


def test_unknown_removed_material_is_blocked(references):
    mass, fees = references
    options = pilot_options().with_columns(existing_material_id=pl.lit("unapproved_generic"))
    with pytest.raises(ContractViolationError, match="removed-material"):
        build_disposal_events(options, mass, fees, CADENCE)


def test_missing_approved_class_maps_are_not_replaced_by_guessed_mapping(tmp_path):
    with pytest.raises(ContractViolationError, match="absent"):
        load_material_mass(CADENCE, tmp_path / "mass.csv", tmp_path / "map.csv", tmp_path / "classes.csv")


def test_mass_unit_inconsistency_is_rejected(tmp_path):
    path = tmp_path / "mass.csv"
    pl.DataFrame({"asset_class": ["roof"], "weight_per_square_lbs": [100.0], "weight_per_sqft_lbs": [2.0]}).write_csv(path)
    with pytest.raises(ContractViolationError, match="inconsistent"):
        read_source_mass(path)


@pytest.mark.parametrize("rul", [0.5, float("nan"), None])
def test_invalid_event_timing_cannot_silently_drop_removal_events(references, rul):
    mass, fees = references
    options = pilot_options().with_columns(initial_rul_years=pl.lit(rul, dtype=pl.Float64))
    with pytest.raises(ContractViolationError):
        build_disposal_events(options, mass, fees, CADENCE)


def test_official_mass_mapping_delegates_to_upstream_without_new_mapping_rules(references, tmp_path):
    # Synthetic mapping fixture exercises the existing upstream mapper, not a
    # replacement approved map for the project's absent source files.
    _, _ = references
    mapping = tmp_path / "map.csv"
    classes = tmp_path / "classes.csv"
    pl.DataFrame({
        "mapping_domain": ["roof_material"] * 3, "source_dataset_id": ["material_mass"] * 3,
        "source_column": ["asset_class"] * 3, "mapping_status": ["approved_exact"] * 3,
        "source_value": ["Architectural Asphalt Shingles", "Metal Roofing", "Clay Tile"],
        "canonical_id": ["test_asphalt", "test_metal", "test_tile"],
        "relationship": ["exact"] * 3, "confidence": ["high"] * 3,
    }).write_csv(mapping)
    pl.DataFrame({
        "mapping_version": ["v1.0.0"] * 3, "aggregation_eligible": [True] * 3,
        "canonical_id": ["test_asphalt", "test_metal", "test_tile"],
        "official_class_id": ["OFFICIAL_ASPHALT", "OFFICIAL_METAL", "OFFICIAL_TILE"],
    }).write_csv(classes)
    result = load_material_mass(CADENCE, SHARED / "material_mass/roofing_lbs.csv", mapping, classes)
    assert dict(zip(result["material_id"], result["weight_per_sqft_lbs"])) == {
        "OFFICIAL_ASPHALT": 2.5, "OFFICIAL_METAL": 1.1, "OFFICIAL_TILE": 8.0,
    }
    assert result["mass_mapping_method"].unique().to_list() == ["approved_cadence_lookup"]
    pl.read_csv(mapping).with_columns(mapping_status=pl.lit("pending")).write_csv(mapping)
    with pytest.raises(ContractViolationError, match="does not resolve"):
        load_material_mass(CADENCE, SHARED / "material_mass/roofing_lbs.csv", mapping, classes)


@pytest.mark.parametrize("case", ["already_charged", "outside_support", "missing_price"])
def test_disposal_attachment_preserves_missingness_and_prevents_double_counting(case):
    annual = pl.DataFrame({"asset_id": ["a"], "decision_year": [2026], "option_id": ["baseline"],
                           "offset": [0], "disposal_real": [0.0]})
    events = annual.with_columns(disposal_real=pl.lit(10.0))
    if case == "already_charged":
        annual = annual.with_columns(disposal_real=pl.lit(1.0))
    elif case == "outside_support":
        events = events.with_columns(offset=pl.lit(1))
    else:
        events = events.with_columns(disposal_real=pl.lit(None, dtype=pl.Float64))
    with pytest.raises(ContractViolationError):
        attach_disposal(annual, events)
