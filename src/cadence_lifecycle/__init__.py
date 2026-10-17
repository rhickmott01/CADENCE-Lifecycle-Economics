"""Standalone lifecycle economics; never mutates the CADENCE stock-flow state."""
from .contracts import LifecycleConfig, ContractViolationError
from .replacement import project_fixed_eul_events
from .cashflows import build_cashflows, compare_options
from .consequences import monetize_consequences, integrate_discrete_hazard
__version__ = "0.1.0"
