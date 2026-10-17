"""Read-only integration boundary. No imports from CADENCE core engine."""
from .contracts import ContractViolationError

def require_approved_mapping(mapping_status: str, proxy_id: str | None):
    if mapping_status != "approved":
        raise ContractViolationError("unapproved material-to-HAZUS mapping")
    if proxy_id is None:
        raise ContractViolationError("explicit proxy or exact mapping ID required")

def cadence_ael_weights_adapter(*args, **kwargs):
    """TODO(open-integration): audit actual CADENCE AEL integration first.

    Never infer annual probability masses from return-period values here.
    """
    raise NotImplementedError("Requires verified CADENCE AEL source-code convention")

def cadence_rul_adapter(*args, **kwargs):
    """TODO(open-integration): CADENCE owns state transitions and burnout precedence."""
    raise NotImplementedError("Requires verified CADENCE RUL transition interface")
