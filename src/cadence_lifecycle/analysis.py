"""Versioned analytical exchange over the existing lifecycle financial engine."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Literal

import duckdb
import polars as pl
from pydantic import BaseModel, ConfigDict, Field

from .cashflows import KEYS, STREAMS, build_cashflows, compare_options
from .contracts import ContractViolationError, require_columns, require_unique
from .disposal import require_finite
from .io import write_run
from .replacement import project_fixed_eul_events, terminal_residual
from .reporting import COMPONENTS, build_component_report, write_contribution_chart

SCHEMA_VERSION = "lifecycle_exchange_v1"
ROOT = Path(__file__).resolve().parents[2]


class AnalysisConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    horizon_years: int = Field(ge=1, le=100)
    real_discount_rate: float = Field(gt=-1, le=1)
    base_dollar_year: int = Field(ge=1900, le=2200)
    baseline_option_id: str = Field(min_length=1)
    assumption_set_id: str = Field(min_length=1)
    data_status: Literal["illustrative", "upstream_validated"]
    source_version: str = Field(min_length=1)
    roof_loss_scope: Literal["roof_exterior_only", "aggregate_building_including_interior"]
    water_loss_scope: Literal["separate_nonoverlapping", "disabled"]
    contents_loss_scope: Literal["separate_water_only", "upstream_total_replaces_water", "disabled"]
    replacement_cost_scope: Literal["installed_excludes_disposal_and_damage"]
    loss_of_use_scope: Literal["temporary_housing_before_insurance", "disabled"]
    event_policy: Literal["fixed_eul_pilot", "upstream_events_and_terminal"]
    overlap_method_id: str = Field(min_length=1)


def _nonempty_strings(frame, columns, label):
    require_columns(frame, columns, label)
    if frame.filter(pl.any_horizontal(*[
        pl.col(c).is_null() | (pl.col(c).cast(pl.String).str.strip_chars() == "") for c in columns
    ])).height:
        raise ContractViolationError(f"{label}: missing identity/provenance")


def evaluate_analysis(options: pl.DataFrame, annual: pl.DataFrame, metadata: pl.DataFrame,
                      config: AnalysisConfig, *, replacement_events: pl.DataFrame | None = None,
                      terminal_values: pl.DataFrame | None = None) -> dict[str, pl.DataFrame]:
    """Complete, explicitly scoped annual costs; no annual hazard model here.

    scenario_id is the upstream physical alternative ID. assumption_set_id is an
    independent sensitivity ID. option_id remains the financial alternative key.
    Metadata grain is KEYS+component, with source/year/method and enabled status.
    """
    _nonempty_strings(options, ["asset_id", "option_id", "scenario_id", "source_version"], "options")
    require_columns(options, ["base_dollar_year"], "options")
    require_unique(options, ["asset_id", "decision_year", "scenario_id"], "scenario crosswalk")
    require_finite(options, ["decision_year", "base_dollar_year"], "option years")
    if options.filter((pl.col("base_dollar_year") != config.base_dollar_year)
                      | (pl.col("decision_year") < config.base_dollar_year)
                      | (pl.col("decision_year") != pl.col("decision_year").floor())).height:
        raise ContractViolationError("Option years disagree with financial dollar basis")
    _nonempty_strings(annual, ["asset_id", "option_id", "source_version"], "annual costs")
    if config.data_status == "upstream_validated":
        for label,frame in [("options",options),("annual costs",annual)]:
            require_columns(frame,["validation_status"],label)
            if frame.filter(pl.col("validation_status").is_null() | (pl.col("validation_status") != "approved")).height:
                raise ContractViolationError("Validated exchange requires explicit upstream approval status")
    require_finite(annual, ["base_dollar_year", "decision_year", "offset"] + STREAMS + ["interior_loss_real"], "annual costs")
    if annual.filter(pl.col("base_dollar_year") != config.base_dollar_year).height:
        raise ContractViolationError("Annual dollar basis mismatch")
    if config.roof_loss_scope == "aggregate_building_including_interior" and annual.filter(pl.col("interior_loss_real") != 0).height:
        raise ContractViolationError("Aggregate building losses overlap separate interior damage")
    disabled = {"interior_loss_real": config.water_loss_scope == "disabled",
                "contents_loss_real": config.contents_loss_scope == "disabled",
                "downtime_real": config.loss_of_use_scope == "disabled"}
    for c, is_disabled in disabled.items():
        if is_disabled and annual.filter(pl.col(c) != 0).height:
            raise ContractViolationError(f"Disabled scope has populated {c}")
    if config.event_policy == "fixed_eul_pilot":
        if config.data_status != "illustrative" or replacement_events is not None or terminal_values is not None:
            raise ContractViolationError("Fixed-EUL policy is an illustrative pilot only")
        events = project_fixed_eul_events(options, config.horizon_years)
        residual = terminal_residual(options, config.horizon_years)
    else:
        if replacement_events is None or terminal_values is None:
            raise ContractViolationError("Production state must supply events and terminal values")
        _nonempty_strings(replacement_events, ["removed_material_id", "material_id", "source_version"], "upstream events")
        _nonempty_strings(terminal_values, ["source_version"], "upstream terminal policy")
        for frame in (replacement_events, terminal_values):
            require_finite(frame, ["base_dollar_year"], "event/terminal dollar basis")
            if frame.filter(pl.col("base_dollar_year") != config.base_dollar_year).height:
                raise ContractViolationError("Event/terminal dollar basis mismatch")
            if config.data_status == "upstream_validated":
                require_columns(frame,["validation_status"],"upstream events/terminal")
                if frame.filter(pl.col("validation_status").is_null() | (pl.col("validation_status") != "approved")).height:
                    raise ContractViolationError("Upstream events/terminal policy lack approval")
        events, residual = replacement_events, terminal_values
    cashflows = build_cashflows(options, annual, config.horizon_years, config.real_discount_rate,
                               replacement_events=events, terminal_values=residual)
    report = build_component_report(cashflows, metadata, config.base_dollar_year, config.baseline_option_id)
    summary = compare_options(cashflows, config.baseline_option_id).with_columns(
        pl.col("npc_real").rank(method="dense").over(["asset_id", "decision_year"]).cast(pl.Int32).alias("investment_rank"))
    components = dict(COMPONENTS, interior_loss=("interior_loss_real", 1))
    long = pl.concat([
        cashflows.select(KEYS + ["offset", pl.col("financial_year").alias("year"), "cashflow_type",
            pl.lit(component).alias("cost_component"),
            (pl.col(column)*sign).alias("annual_cost_real"),
            (pl.col(column)*sign*pl.col("discount_factor")).alias("discounted_cost_real")])
        for component,(column,sign) in components.items()
    ]).join(metadata.rename({"component":"cost_component"}),on=KEYS+["cost_component"],validate="m:1")
    long = long.with_columns(pl.when(pl.col("enabled")).then(pl.lit("complete")).otherwise(pl.lit("disabled")).alias("completeness_status"))
    crosswalk = options.select(KEYS + ["scenario_id"])
    tables = {"options":options, "annual_costs":annual, "annual_cashflows":cashflows,
              "annual_lifecycle_cashflows":long, "lifecycle_summary":summary,
              "npv_contributions":report, "component_metadata":metadata, "replacement_events":events,
              "terminal_values":residual,
              "annual_damage_components":annual.select(KEYS + ["offset", "source_version", "building_loss_real", "interior_loss_real", "contents_loss_real", "downtime_real"])
                  .with_columns((pl.col("decision_year")+pl.col("offset")).alias("year"))}
    for name, frame in tables.items():
        if "scenario_id" not in frame.columns:
            frame = frame.join(crosswalk,on=KEYS,validate="m:1")
        tables[name] = frame.with_columns(
            pl.lit(config.assumption_set_id).alias("assumption_set_id"),
            pl.lit(config.data_status).alias("data_status"),
            pl.lit(config.base_dollar_year).alias("base_dollar_year"),
            pl.lit(SCHEMA_VERSION).alias("exchange_schema_version"),
            pl.lit(config.source_version).alias("analysis_source_version"),
        ).sort([c for c in KEYS + ["offset", "cost_component", "component"] if c in frame.columns])
    return tables


def validate_exchange_tables(tables: dict[str, pl.DataFrame]) -> None:
    """Validate the public logical schema before serialization, independently of I/O."""
    requirements = {
        "options": (KEYS,["scenario_id","source_version"]),
        "annual_costs": (KEYS+["offset"],STREAMS+["interior_loss_real"]),
        "annual_cashflows": (KEYS+["offset"],["discounted_real","total_real"]),
        "annual_lifecycle_cashflows": (KEYS+["offset","cost_component"],
            ["year","annual_cost_real","discounted_cost_real","source","source_year","valuation_method","completeness_status"]),
        "lifecycle_summary": (KEYS,["npc_real","incremental_npv_real","investment_rank"]),
        "npv_contributions": (KEYS+["component"],["baseline_pv_real","option_pv_real","npv_contribution_real","status"]),
        "component_metadata": (KEYS+["component"],["enabled","source","source_year","valuation_method"]),
        "replacement_events": (KEYS+["offset"],["event_cost_real"]),
        "terminal_values": (KEYS,["terminal_value_real"]),
        "annual_damage_components": (KEYS+["offset"],["year","building_loss_real","interior_loss_real","contents_loss_real","downtime_real"]),
    }
    for name,(keys,columns) in requirements.items():
        if name not in tables:
            raise ContractViolationError(f"Missing exchange table: {name}")
        frame=tables[name]
        require_unique(frame,keys,name)
        require_columns(frame,columns+["scenario_id","assumption_set_id","data_status","base_dollar_year","exchange_schema_version"],name)
        _nonempty_strings(frame,["asset_id","option_id","scenario_id","assumption_set_id"],name)
        for c in ["asset_id","option_id","scenario_id","assumption_set_id"]:
            if frame.schema[c] != pl.String:
                raise ContractViolationError(f"{name}: identifier {c} must be a string")
        numeric=[c for c in columns if c.endswith("_real")]
        if numeric:
            require_finite(frame,numeric,name)
        if frame.filter(pl.col("exchange_schema_version") != SCHEMA_VERSION).height:
            raise ContractViolationError("Unsupported exchange schema version")
    summary=tables["lifecycle_summary"]
    totals=tables["npv_contributions"].group_by(KEYS).agg(
        pl.col("npv_contribution_real").sum().alias("contribution_total"),
        pl.col("option_pv_real").sum().alias("component_total"))
    totals=summary.join(totals,on=KEYS,how="left",validate="1:1")
    if totals.filter(pl.col("contribution_total").is_null() | pl.col("component_total").is_null()
            | ((pl.col("contribution_total")-pl.col("incremental_npv_real")).abs()>1e-8+1e-10*pl.col("incremental_npv_real").abs())
            | ((pl.col("component_total")-pl.col("npc_real")).abs()>1e-8+1e-10*pl.col("npc_real").abs())).height:
        raise ContractViolationError("Export summary and component totals do not reconcile")
    wide=tables["annual_cashflows"].group_by(KEYS).agg(pl.col("discounted_real").sum().alias("wide_npc"))
    long=tables["annual_lifecycle_cashflows"].group_by(KEYS).agg(pl.col("discounted_cost_real").sum().alias("long_npc"))
    totals=summary.join(wide,on=KEYS,how="left",validate="1:1").join(long,on=KEYS,how="left",validate="1:1")
    if totals.filter(pl.col("wide_npc").is_null() | pl.col("long_npc").is_null()
            | ((pl.col("wide_npc")-pl.col("npc_real")).abs()>1e-8+1e-10*pl.col("npc_real").abs())
            | ((pl.col("long_npc")-pl.col("npc_real")).abs()>1e-8+1e-10*pl.col("npc_real").abs())).height:
        raise ContractViolationError("Export cash flows and NPC totals do not reconcile")


def publish_analysis(output_root: Path, tables: dict[str, pl.DataFrame], config: AnalysisConfig,
                     sources: dict[str, str], *, chart: bool = True) -> Path:
    """Write once, verify Parquet roundtrips and DuckDB joins before publication."""
    import tempfile
    output_root = Path(output_root).resolve()
    if not output_root.is_relative_to(ROOT):
        raise ContractViolationError("Analysis outputs must stay inside CADENCE-Lifecycle-Economics")
    validate_exchange_tables(tables)
    tables={name:frame.sort([c for c in ["sensitivity_case_id"]+KEYS+["offset","year","wind_speed_mph","event_id","cost_component","component"] if c in frame.columns])
            if any(c in frame.columns for c in KEYS+["sensitivity_case_id"]) else frame for name,frame in tables.items()}
    identities = dict(sources)
    for path in sorted((ROOT / "src/cadence_lifecycle").glob("*.py")):
        identities[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name, frame in sorted(tables.items()):
        identities[f"table:{name}"] = hashlib.sha256(frame.write_json().encode()).hexdigest()
    settings = dict(config.model_dump(), exchange_schema_version=SCHEMA_VERSION,
        package_versions={name:importlib.metadata.version(name) for name in ("polars","duckdb","pyarrow","pydantic","numpy","matplotlib")})
    # Match the existing immutable publisher's identity, including all input tables.
    payload=json.dumps({"config":settings,"inputs":identities,"package_version":"0.1.0"},sort_keys=True)
    run_id=hashlib.sha256(payload.encode()).hexdigest()[:24]
    tables={k:v.with_columns(pl.lit(run_id).alias("run_id")) for k,v in tables.items()}
    output_root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_root) as staging:
        target=write_run(staging,settings,identities,tables)
        with duckdb.connect() as db:
            for name, frame in tables.items():
                path=target/f"{name}.parquet"
                actual=pl.read_parquet(path)
                if not actual.equals(frame):
                    raise ContractViolationError(f"Parquet roundtrip failed: {name}")
                db.read_parquet(str(path)).create_view(name)
                if db.sql(f'SELECT count(*) FROM "{name}"').fetchone()[0] != frame.height:
                    raise ContractViolationError(f"DuckDB row mismatch: {name}")
            missing=db.sql('''SELECT count(*) FROM annual_lifecycle_cashflows c
                LEFT JOIN options o USING(run_id,asset_id,decision_year,option_id,scenario_id,assumption_set_id)
                WHERE o.source_version IS NULL''').fetchone()[0]
            if missing:
                raise ContractViolationError("Export identities do not join to options")
        if chart:
            write_contribution_chart(tables["npv_contributions"],target/"npv_contributions.svg",
                config.baseline_option_id,preview_path=target/"npv_contributions.png",
                subtitle=f"{config.data_status}; {config.assumption_set_id}; uncalibrated water model")
        for name in ("lifecycle_summary","npv_contributions","replacement_events"):
            tables[name].write_csv(target/f"{name}.csv")
        schema={name:{"rows":frame.height,"columns":{c:str(t) for c,t in frame.schema.items()}} for name,frame in tables.items()}
        (target/"schemas.json").write_text(json.dumps(schema,indent=2,sort_keys=True)+"\n")
        checksums={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.iterdir())}
        (target/"artifact_checksums.json").write_text(json.dumps(checksums,indent=2,sort_keys=True)+"\n")
        for source, expected in sources.items():
            if Path(source).is_absolute() and Path(source).is_file() and hashlib.sha256(Path(source).read_bytes()).hexdigest() != expected:
                raise ContractViolationError(f"Source changed during analysis: {source}")
        published=output_root/f"schema_version={SCHEMA_VERSION}"/target.name
        published.parent.mkdir(parents=True,exist_ok=True)
        if published.exists():
            raise ContractViolationError(f"write-once run already exists: {published}")
        target.rename(published)
    return published
