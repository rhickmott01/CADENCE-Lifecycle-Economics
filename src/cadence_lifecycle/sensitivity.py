"""Reproducible illustrative uncertainty, with no implied calibration."""
import random

import polars as pl

from .contracts import ContractViolationError
from .demo import SCENARIOS, demo_inputs


def sample_assumptions(samples: int, seed: int) -> list[dict]:
    """Independent triangular priors from the explicit demo endpoints/mode.

    Assumed distributions, not fitted uncertainty. Bundled endpoints need not be
    monotonic NPV bounds; nonlinear water thresholds affect rankings.
    """
    if samples < 1 or samples > 10000:
        raise ContractViolationError("samples must be between 1 and 10000")
    rng=random.Random(seed)
    result=[]
    for _ in range(samples):
        row={}
        for key,mode in SCENARIOS["central"].items():
            low=min(s[key] for s in SCENARIOS.values())
            high=max(s[key] for s in SCENARIOS.values())
            row[key]=rng.triangular(low,high,mode)
        result.append(row)
    return result


def evaluate_sensitivity(shared_root, cadence_root, *, horizon=30, samples=0, seed=20261104):
    """One-at-a-time endpoint cases plus optional seeded joint draws."""
    cases=[("central","central",SCENARIOS["central"])]
    for parameter in SCENARIOS["central"]:
        for end in ("low","high"):
            cases.append((parameter,end,{parameter:SCENARIOS[end][parameter]}))
    if samples:
        cases.extend(("joint",str(i),s) for i,s in enumerate(sample_assumptions(samples,seed)))
    results=[]
    for i,(parameter,level,overrides) in enumerate(cases):
        tables,_,_=demo_inputs(shared_root,cadence_root,"central",horizon=horizon,overrides=overrides)
        results.append(tables["lifecycle_summary"].with_columns(
            pl.lit(i).alias("sensitivity_case_id"),pl.lit(parameter).alias("varied_parameter"),
            pl.lit(level).alias("sensitivity_level"),pl.lit(seed).alias("random_seed"),
            pl.lit("assumed_triangular_independent" if parameter=="joint" else "assumed_OAT_endpoint").alias("uncertainty_method")))
    return pl.concat(results,how="diagonal_relaxed")
