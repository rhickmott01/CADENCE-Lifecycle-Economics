# Assumptions and blockers

| Area | Status | Rule |
|---|---|---|
| Separate repository | APPROVED | Never modify main CADENCE |
| Horizon | APPROVED | 30 periods + terminal valuation |
| Financial basis | APPROVED | Constant real dollars / real discount |
| Terminal | APPROVED | Straight-line remaining service value |
| Baseline | APPROVED | Keep existing roof, replace at burnout |
| Production RUL | BLOCKED | Audit and reuse CADENCE RUL/degradation; fixed EUL is pilot only |
| AEL | BLOCKED | Audit existing CADENCE AEL; no new hazard integration policy |
| Above age 30 | APPROVED | Flag/block unsupported vulnerability |
| Five measures | APPROVED | Independently selectable, units preserved |
| Maintenance | APPROVED | Explicit source/input or disabled |
| Salvage | APPROVED | Explicit source/input or disabled |
| Stakeholder | APPROVED | Asset owner first |
| Metal/tile proxies | BLOCKED | Source-aware mapping approval required |
| Double-counting | BLOCKED | Verify building/content/downtime/debris coverage |
| Burnout vs upgrade precedence | OPEN CADENCE | Do not choose in adapter |
| Hazard interpolation | OPEN CADENCE | Do not choose in adapter |
| Prefect ingestion boundary | OPEN CADENCE | Do not choose in adapter |
| Terminal eligible cost basis | PILOT | Replacement price for new roof; separate existing-roof basis |
| Annual cash-flow timing | PILOT | offset t; must reconcile with CADENCE |
| BCR/payback | DEFERRED | Requires approved positive/negative stream classification |

## Loss-of-use scope confirmed November 3, 2026

- County and housing size must be configurable. The demonstration uses Durham County FIPS `37063`, one two-bedroom household, and the shared HUD-derived 2025 source rate of $62.40/day before dollar-year conversion.
- Include storm-related extra temporary housing costs before insurance reimbursements. Planned roof-work displacement, moving/storage, meals, and insurance effects are outside this initial scope.
- Validate HAZUS loss-of-use definitions, source-aware roof mappings, and annual hazard probabilities before using HAZUS-derived annual expected displacement days. Repair duration alone does not establish displacement duration or an upgrade benefit.
- Convert the housing source rate to the common 2026 financial base with a documented method, then hold it constant in real terms. The specific conversion index and period still need source validation; no conversion factor is approved or applied yet.
- The existing 30-year horizon, 3% real discount rate, and offset-t financial convention remain the starting configuration.
- The user reports that the full HAZUS Parquet dataset is in Duke Box. Local source access is pending. Start with a targeted partition and inventory required climate-zone/age files before reading broadly. Treat source files as read-only and write derived outputs only in this repository.
- No loss-of-use NPV result has been produced from these assumptions yet. Missing displacement inputs remain missing, not zero.
