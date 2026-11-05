import pytest
from cadence_lifecycle.contracts import ContractViolationError
from cadence_lifecycle.sensitivity import sample_assumptions
from cadence_lifecycle.demo import SCENARIOS


def test_reproducible_assumed_distributions_within_explicit_ranges():
    first=sample_assumptions(20,42)
    assert first==sample_assumptions(20,42)
    assert first!=sample_assumptions(20,43)
    for sample in first:
        for key,value in sample.items():
            assert min(s[key] for s in SCENARIOS.values()) <= value <= max(s[key] for s in SCENARIOS.values())


def test_invalid_sample_count():
    with pytest.raises(ContractViolationError):sample_assumptions(0,42)
