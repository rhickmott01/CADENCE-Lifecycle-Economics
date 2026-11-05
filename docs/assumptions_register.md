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
- The supplied Duke Box partition `/Users/robhickmott/Library/CloudStorage/Box-Box/Fragility_Curves/iecc2021/1A/age_01` is readable and has been structurally inspected. It contains 7,160 loss-of-use curves with raw responses from 0 to 720; its schema has no explicit response-unit field. This does not establish Durham applicability, residential displacement semantics, or an approved roof mapping. Treat source files as read-only and inspect only selected partitions.
- No loss-of-use NPV result has been produced from these assumptions yet. Missing displacement inputs remain missing, not zero.
- The user confirmed that upstream inputs will supply the needed hazard/climate/scenario calculations, which remain in their owning repositories. The preferred lifecycle input is a validated annual displacement-days export, or an already-valued annual cost export; do not require raw wind grids or recreate annualization here. See [loss_of_use_integration.md](loss_of_use_integration.md).
- For the annual-days interface, upstream must allocate displacement to financial years, including multi-year events and overlapping periods. The adapter checks within-year days against the calendar-year length and rejects raw long event durations rather than clipping them. An occurrence-year valuation of the entire future displacement stream is a different timing contract requiring explicit review.

## Full lifecycle research extension — November 4, 2026

The user's autonomous development request authorizes property/interior and
contents modeling, research, tests, analytical exports, and incremental commits
and pushes on `feature/cost-driver-analysis`. This extends the earlier narrow
scope. Production integration and predictive calibration remain separate.

| Assumption | Value / relationship and units | Source / status | Sensitivity and validation need |
| --- | --- | --- | --- |
| Interior damage | `clip(x^5/2 + 0.6785x,0,1)`, x=retained/capacity | Abreu 2019 p42 eq2; source equation with explicit implementation cap | Check component loss data; printed equation exceeds 1 near saturation |
| Contents damage | `clip(sin(x)^1.5/2 + x^20,0,1)`; radians | Abreu 2019 p42 eq3; source equation with implementation cap | Strong threshold sensitivity; independent inventories needed |
| Cabinet / electrical weights | Floor/partitions .6/.4; ceiling/partitions .4/.6 | Thesis p42 engineering assumptions, uncalibrated | Validate actual component locations |
| Reduced geometry | Single story, one wetted footprint 150 m² | Explicit demonstration assumption replacing thesis six compartments | Resolve spatial/directional transport and exposed-value allocation |
| Roof opening paths | `A[b+(1-b)ck]`, m² | Implementation reduction of area/rain relationships; no published equation claim | Upstream physical breach/underlayment validation required |
| Entry | `A_eff * effective incident rain * eta`, liters; k=.05, eta=.8 | Dimensional volume equation; entry parameters assumed | Test penetration/runoff mechanisms |
| Capacity densities | Ceiling .5, partitions .3, contents 1, flooring .2 L/m² footprint, central | Assumed, not imported calibrated gypsum capacities | Multiply by 1.5/1/.5 in low/central/high |
| Propagation | Ceiling → partitions → contents → floor; positive excess only | Thesis p39; one-story adaptation | Validate order and rate, drying, compartments |
| Interior exposures | Ceiling 15k, partitions 25k, floor 15k, cabinets 15k, electrical 10k USD | Synthetic replacement values, 2024 real, within wetted footprint | Replace with asset inventory and regional repair costs |
| Contents exposure | 30k/50k/80k USD in low/central/high | Explicit synthetic inventories in wetted footprint; no interior-dollar multiplier | Requires asset inventory/calibrated valuation scenarios |
| Physical damage / rain | No storm / 100 / 140 mph fixture; effective rain 0/100/250 mm | Synthetic joint event states; not a fitted fragility or wind-rain relationship | Upstream joint distribution and climate treatment required |
| Annual event masses | .97/.025/.005, mutually exclusive including no-storm | Synthetic annual-maximum fixture, existing integrator | Not RP reciprocals; does not represent multiple storms/year |
| Fixture option effects | Old baseline 1.4 until existing RUL; new asphalt 1; metal .4 | Explicit assumed damage multiplier; no approved metal HAZUS mapping claim | Very sensitive; source-specific upstream proxy approval needed |
| Installed costs / EUL | 12k asphalt / 25k metal USD; new EUL 20/40 years, baseline RUL8 | Existing pilot assumptions, re-declared synthetic 2024 real | EUL multipliers .9/1/1.1; production state supplied upstream |
| Maintenance | 120/year asphalt, 80/year metal, central | Synthetic 2024 USD; no hidden material/labor split | Multipliers .5/1/1.5 |
| Housing | Durham two-bedroom 62.40 USD/day, 2025; factor1 into 2024 demo | Real source rate; explicitly illustrative equal-dollar proxy, not CPI | Production conversion remains pending; original 2026 conversion not invented |
| Disposal | NC39.71 USD/short ton, source2024; asphalt2.5 lb/ft² | Shared CSV and unmodified CADENCE helper; exact subtypes | Tipping only; excludes transport/tear-off labor; changed removed material tracked |
| Downtime | Conditional fixture 0/7/45 days, adjusted by option/scenario | Synthetic, existing expected-days monetization | Multipliers .5/1/1.5; validated upstream annual days needed |
| Real discounting | 1%/3%/5%; 30 periods + terminal at30 | Assumed; offset-t existing engine | OAT and joint sensitivity; align production horizon/terminal policy |
| Terminal value | Remaining service fraction × eligible basis; no terminal-boundary replacement | Existing pilot policy; upstream may explicitly supply zero instead | Must reconcile with CADENCE's no-credit policy |
| Monte Carlo | Independent triangular endpoints/mode, seed20261104 | Assumed distributions; reproducible mechanics, not estimated confidence | Replace with fitted distributions and dependencies |
| Exclusions | Casualty, insurance, carbon, transport/tear-off labor, hazard debris | Explicit disabled/unmodeled scope | No unsupported zero-valued production claims |

The original supplied PDF has SHA-256
`ad1a7e68564bb1af20ab3d7b8308dcc1eb6cbd1622c81975556ef5fb51b368d2`.
See [methodology](water_damage_methodology.md),
[exchange contract](lifecycle_exchange_v1.md), and
[compatibility audit](portfolio_compatibility.md). Unit tests validate implementation
properties, not scientific predictive accuracy.

Additional isolated sensitivity controls vary the **supplied** roof-damage fixture
by .75/1/1.25 and existing-roof RUL by 6/8/10 years. These controls do not implement
a wind/fragility producer. They make upstream damage uncertainty and the timing of
the first baseline replacement explicit, in addition to the eight controls above.
