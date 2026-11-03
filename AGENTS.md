# Engineering rules

Read [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) before changing economic behavior. It records the research objectives, local audit, modeling differences, and integration roadmap.

- Modify only `CADENCE-Lifecycle-Economics`. Main `CADENCE`, `Economic-Externalities-Research-Database`, `Installation_Cost_Research_Database_CADENCE`, and `cadence_shared_data` are read-only, including their data and outputs.
- This package is an independent development environment. CADENCE retains ownership of production stock-flow state, replacement/adoption decisions, and its existing economics engine.
- Reuse approved CADENCE material mappings and calculations through explicit interfaces; do not duplicate research extraction pipelines or infer unapproved mappings.
- Preserve source/version provenance, units, geographic identifiers (including leading-zero FIPS), source and financial base years, discount timing, and missing-data status. Select geographic observations deterministically; reject unresolved ambiguity.
- Distinguish disabled streams from missing observations. Do not silently turn missing costs into zero or invent prices, attribution factors, or material/labor splits. Label synthetic pilot inputs explicitly.
- Avoid double-counting installation, disposal, repair, debris, and displacement costs. Keep community casualty baseline risk separate from attributable roof-upgrade benefits until a defensible method is approved.
- Reconcile timing, terminal value, hazard integration, and repair valuation before claiming CADENCE equivalence. Keep provisional assumptions and uncertainty visible.
- For economic changes, run relevant tests and verify that component contributions sum to total incremental NPV, with positive values favoring the upgrade. Preserve existing user changes.
- Do not commit, push, or modify another repository without explicit user approval.
- Approved implementation scope: component reporting and automatic disposal events on `feature/cost-driver-analysis`. Next modeling priorities are property damage beyond the roof, contents damage, and loss of use. Casualty-risk work is deferred. Production integration needs reconciliation and approval.
