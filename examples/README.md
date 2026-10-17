# Pilot workflow

Create two option rows per asset: `baseline` (keep until burnout) and `upgrade` (replace immediately). Provide an annual-cost row for each option and each offset 0..29, with **explicit zero** values for disabled streams. Use `project_fixed_eul_events`, `build_cashflows`, then `compare_options`. The tests in `tests/test_cashflows.py` are an executable minimal example.

Do not use the discrete hazard integrator until approved probability masses are available from CADENCE. Do not use provisional metal/tile fragility proxies without approved source mappings.
