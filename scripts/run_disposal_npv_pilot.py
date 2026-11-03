"""Compatibility entry point using generated disposal events and the full report.

Historical outputs/disposal_npv_pilot artifacts are preserved.
New results use versioned outputs/cost_driver_analysis runs.
"""
from cadence_lifecycle.pilot import main

if __name__ == "__main__":
    main()
