import pytest
from cadence_lifecycle.adapter import require_approved_mapping,cadence_ael_weights_adapter
from cadence_lifecycle.contracts import ContractViolationError

def test_unapproved_proxy_blocked():
 with pytest.raises(ContractViolationError):require_approved_mapping("draft","SERBL")
def test_unverified_ael_blocked():
 with pytest.raises(NotImplementedError):cadence_ael_weights_adapter()
