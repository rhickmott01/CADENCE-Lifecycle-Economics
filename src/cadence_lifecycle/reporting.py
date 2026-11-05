"""Auditable attribution of existing lifecycle cash flows; no new pricing engine."""

from pathlib import Path

import polars as pl

from .cashflows import KEYS, STREAMS, compare_options
from .contracts import ContractViolationError, require_columns, require_unique
from .disposal import require_finite

# Amounts remain positive in the cash-flow API; credits have negative cost signs.
COMPONENTS = {c.removesuffix("_real"): (c, -1 if c == "salvage_credit_real" else 1)
              for c in STREAMS}
COMPONENTS.update(replacement=("replacement_real", 1),
                  terminal_service_value=("terminal_credit_real", -1))
META = ["enabled", "source", "source_year", "valuation_method"]


def build_component_report(cashflows: pl.DataFrame, metadata: pl.DataFrame,
                           base_dollar_year: int,
                           baseline_option_id: str = "baseline") -> pl.DataFrame:
    """Report baseline PV minus option PV per component, reconciled to compare_options.

    Metadata has one row per KEYS + component, with enabled (bool), source,
    source_year (nullable integer), and valuation_method. Disabled costs must be
    explicit zeros. Enabled missing/nonfinite values fail closed. Cash-flow
    discount factors are reused, including at zero discount and zero-cost years.
    """
    components = dict(COMPONENTS)
    if "interior_loss_real" in cashflows.columns:
        components["interior_loss"] = ("interior_loss_real", 1)
    numeric = [column for column, _ in components.values()]
    require_unique(cashflows, KEYS + ["offset"], "cashflows")
    require_finite(cashflows, numeric + ["total_real", "discounted_real", "discount_factor"], "cashflows")
    if cashflows.is_empty() or not 1900 <= base_dollar_year <= 2200:
        raise ContractViolationError("Nonempty cashflows and an explicit financial base year required")
    require_columns(cashflows, ["cashflow_type"], "cashflows")
    require_finite(cashflows, ["offset"], "cashflow offsets")
    if cashflows.filter(
        pl.any_horizontal(*[pl.col(k).is_null() for k in KEYS + ["cashflow_type"]])
        | ~pl.col("cashflow_type").is_in(["annual", "terminal"])
        | (pl.col("offset") != pl.col("offset").floor())
    ).height:
        raise ContractViolationError("Invalid cash-flow identity/type/offset")
    support = cashflows.group_by(KEYS).agg(
        pl.col("offset").min().alias("first"), pl.col("offset").max().alias("last"),
        pl.len().alias("count"), (pl.col("cashflow_type") == "terminal").sum().alias("terminal_count"),
        pl.col("offset").filter(pl.col("cashflow_type") == "terminal").max().alias("terminal_offset"),
    )
    if support.filter(
        (pl.col("first") != 0) | (pl.col("count") != pl.col("last") + 1)
        | (pl.col("terminal_count") != 1) | (pl.col("terminal_offset") != pl.col("last"))
    ).height or support.group_by(["asset_id", "decision_year"]).agg(
        pl.col("last").n_unique().alias("horizons")
    ).filter(pl.col("horizons") != 1).height:
        raise ContractViolationError("Cash-flow support must be complete with one common terminal boundary")
    if cashflows.filter(
        ((pl.col("cashflow_type") == "annual") & (pl.col("terminal_credit_real") != 0))
        | ((pl.col("cashflow_type") == "terminal") & pl.any_horizontal(
            *[pl.col(c) != 0 for c in numeric if c != "terminal_credit_real"]))
    ).height:
        raise ContractViolationError("Terminal credit and annual costs must use their proper rows")
    if cashflows.filter(pl.col("discount_factor") <= 0).height:
        raise ContractViolationError("Invalid discount factor")
    if cashflows.filter(pl.any_horizontal(*[pl.col(c) < 0 for c in numeric])).height:
        raise ContractViolationError("Cost/credit magnitudes must be nonnegative")
    signed = [pl.col(column) * sign for column, sign in components.values()]
    bad = cashflows.filter(
        ((pl.sum_horizontal(*signed) - pl.col("total_real")).abs()
         > 1e-8 + 1e-10 * pl.col("total_real").abs())
        | ((pl.col("total_real") * pl.col("discount_factor") - pl.col("discounted_real")).abs()
           > 1e-8 + 1e-10 * pl.col("discounted_real").abs())
    )
    if bad.height:
        raise ContractViolationError("Cash-flow components/discount factors do not reconcile")
    annual = pl.concat([
        cashflows.select(
            KEYS + ["offset", pl.lit(component).alias("component"),
                    (pl.col(column) * sign).alias("signed_cost_real"),
                    (pl.col(column) * sign * pl.col("discount_factor")).alias("component_pv_real")]
        ) for component, (column, sign) in components.items()
    ])
    keys = KEYS + ["component"]
    require_unique(metadata, keys, "component metadata")
    require_columns(metadata, keys + META, "component metadata")
    expected = annual.select(keys).unique()
    if (expected.join(metadata.select(keys), on=keys, how="anti").height
            or metadata.join(expected, on=keys, how="anti").height):
        raise ContractViolationError("Metadata must exactly cover all option components")
    if metadata.schema["enabled"] != pl.Boolean or metadata.filter(
        pl.col("enabled").is_null() | pl.col("source").is_null()
        | (pl.col("source").str.len_chars() == 0)
        | pl.col("valuation_method").is_null()
        | (pl.col("valuation_method").str.len_chars() == 0)
    ).height:
        raise ContractViolationError("Explicit enabled status, source and valuation method required")
    annotated = annual.join(metadata, on=keys, validate="m:1")
    if annotated.filter(~pl.col("enabled") & (pl.col("signed_cost_real") != 0)).height:
        raise ContractViolationError("Disabled components must contain only zero costs")
    summary = annotated.group_by(keys).agg(
        pl.col("component_pv_real").sum().alias("option_pv_real"),
        *[pl.col(c).first() for c in META],
    )
    baseline = summary.filter(pl.col("option_id") == baseline_option_id).drop("option_id").rename(
        {"option_pv_real": "baseline_pv_real", **{c: f"baseline_{c}" for c in META}}
    )
    result = summary.join(
        baseline, on=["asset_id", "decision_year", "component"], how="left", validate="m:1"
    ).with_columns(
        (pl.col("baseline_pv_real") - pl.col("option_pv_real")).alias("npv_contribution_real"),
        pl.lit(base_dollar_year).alias("base_dollar_year"),
        pl.lit("USD_real").alias("unit"),
        pl.when(pl.col("enabled")).then(pl.lit("complete")).otherwise(pl.lit("disabled"))
        .alias("status"),
        pl.lit("offset_t; terminal_credit_at_horizon").alias("discount_timing"),
    )
    # Authoritative total remains the existing lifecycle comparison.
    totals = compare_options(cashflows, baseline_option_id)
    reconciled = result.group_by(KEYS).agg(
        pl.col("npv_contribution_real").sum().alias("contribution_sum_real"),
        pl.col("option_pv_real").sum().alias("component_npc_real"),
    ).join(totals, on=KEYS, validate="1:1")
    if reconciled.filter(
        ((pl.col("contribution_sum_real") - pl.col("incremental_npv_real")).abs()
         > 1e-8 + 1e-10 * pl.col("incremental_npv_real").abs())
        | ((pl.col("component_npc_real") - pl.col("npc_real")).abs()
           > 1e-8 + 1e-10 * pl.col("npc_real").abs())
    ).height:
        raise ContractViolationError("Component PV/NPV totals do not reconcile")
    return result.join(totals, on=KEYS, validate="m:1").sort(keys)


def write_contribution_chart(report: pl.DataFrame, output_path: Path,
                             baseline_option_id: str = "baseline", *,
                             preview_path: Path | None = None,
                             subtitle: str = "See contribution table for stream status and provenance") -> None:
    """Standalone Matplotlib SVG: per-component bars, net marker, explicit pilot label."""
    import os
    import tempfile

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Font/config caches stay alongside the requested output, never in user HOME.
    with tempfile.TemporaryDirectory(dir=output_path.parent) as cache:
        previous = os.environ.get("MPLCONFIGDIR")
        os.environ["MPLCONFIGDIR"] = cache
        try:
            import matplotlib
            from matplotlib.figure import Figure

            with matplotlib.rc_context({"svg.hashsalt": "cadence-cost-driver-v1", "font.family": "DejaVu Sans"}):
                groups = report.filter(pl.col("option_id") != baseline_option_id).partition_by(KEYS, maintain_order=True)
                if not groups:
                    raise ContractViolationError("A chart requires at least one nonbaseline option")
                figure = Figure(figsize=(11, 4.8 * len(groups)), layout="constrained")
                axes = figure.subplots(len(groups), 1, squeeze=False)
                for ax, group in zip(axes[:, 0], groups):
                    active = group.filter(pl.col("enabled") | pl.col("baseline_enabled"))
                    values = active["npv_contribution_real"].to_list()
                    names = {"building_loss": "Roof / exterior loss", "downtime": "Loss of use"} if "interior_loss" in group["component"] else {}
                    labels = [names.get(c, c.replace("_", " ").title()) for c in active["component"]]
                    net = group["incremental_npv_real"][0]
                    ax.barh(labels, values, color=["#147d64" if v >= 0 else "#b44a42" for v in values])
                    ax.scatter([net], ["Net incremental NPV"], marker="D", color="#172b4d", s=65, zorder=3)
                    for label, value in zip(labels + ["Net incremental NPV"], values + [net]):
                        ax.annotate(f"${value:,.2f}", (value, label), xytext=(5 if value >= 0 else -5, 0),
                                    textcoords="offset points", ha="left" if value >= 0 else "right", va="center")
                    ax.axvline(0, color="#444444", linewidth=0.8)
                    ax.margins(x=0.25)
                    ax.invert_yaxis()
                    ax.set_title(f"{group['asset_id'][0]} · {group['decision_year'][0]} · {group['option_id'][0]}")
                    ax.set_xlabel(f"Incremental NPV contribution ({group['base_dollar_year'][0]} real USD); positive favors upgrade")
                    ax.spines[["top", "right"]].set_visible(False)
                figure.suptitle(f"Roofing cost drivers\n{subtitle}", fontsize=12)
                figure.savefig(output_path, format="svg", metadata={"Date": None, "Creator": "CADENCE lifecycle cost-driver report"})
                if preview_path is not None:
                    figure.savefig(preview_path, format="png", dpi=150,
                                   metadata={"Software": "CADENCE lifecycle cost-driver report"})
        finally:
            if previous is None:
                os.environ.pop("MPLCONFIGDIR", None)
            else:
                os.environ["MPLCONFIGDIR"] = previous
