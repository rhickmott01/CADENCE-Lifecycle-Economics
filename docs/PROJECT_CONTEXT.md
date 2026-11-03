# CADENCE lifecycle economics project context

## Research objective and ownership

Develop a dynamic lifecycle economic model explaining which costs and benefits influence residential roofing upgrades under changing climate hazards. Approved functionality ultimately belongs in [main CADENCE](https://github.com/Ajjme/CADENCE).

This repository is an independent development environment, not a replacement for CADENCE's economics or stock-flow engines. CADENCE owns production state transitions and adoption decisions. The Economic Externalities Research Database supplies source-data research; reuse its products rather than duplicating extraction pipelines. Installation Cost Research supplies installation-cost research context. All sibling repositories and shared datasets remain read-only. Only this repository may be modified; commits and pushes require user approval.

## Scientific priorities

1. **Property damage beyond the roof and contents losses:** identify supported asset-level consequence measures and exposure values, reusing existing CADENCE/HAZUS calculations wherever appropriate. Establish which losses a roof upgrade can change, and separate non-roof damage from already counted roof repair/replacement costs. FEMA property-risk estimates may inform research, but community aggregates must not be assigned directly as avoided losses for an individual roof upgrade.
2. **Loss of use:** reuse CADENCE monetization, HAZUS downtime curves, and HUD-derived county relocation costs. Preserve downtime units and the distinction between missing expected days and a disabled stream.
3. **Roof disposal:** reuse CADENCE material-mass mappings and EREF tipping fees; charge the material actually removed at each replacement event.
4. **Lifecycle dynamics:** represent replacement timing, remaining useful life, maintenance, terminal residual value, and lifetime costs under changing hazards.
5. **Decision explanation:** produce an auditable component-level incremental NPV breakdown showing which factors favor or discourage an upgrade.

Direction updated November 2, 2026: the user clarified that property damage and loss of use are the next priorities, rather than casualty risk. The earlier [casualty research specification](casualty_research_plan.md) is retained as deferred background. No casualty attribution method or factor is approved.

## Local repository audit

Audit recorded November 1, 2026. Local HEAD references: lifecycle `b6182e0de08015c6208a88f1c1123ee99e6924cc`; CADENCE `33eeae6a5eae5d9758c59c97948ba5516714ba3a`. Lifecycle already had uncommitted changes and untracked pilots/outputs; its HEAD alone does not identify the full inspected working tree. These are local findings, not verification of the current GitHub branch.

### Lifecycle implementation

- `src/cadence_lifecycle/replacement.py`: vectorized fixed-EUL pilot events and straight-line terminal service value, with a separate existing-roof basis. Replacements at the terminal boundary are excluded.
- `src/cadence_lifecycle/cashflows.py`: annual stream assembly, discounted net present cost (NPC), and baseline comparisons. A 30-year run has offsets 0–29 and terminal credit at 30. Implementation discounts operating and replacement costs at offset `t`; its “year-end” docstring conflicts with this convention.
- `src/cadence_lifecycle/consequences.py`: supplied discrete hazard-mass integration and monetization of building loss, contents loss, downtime, and two debris measures. This is not verified equivalent to CADENCE hazard integration.
- `src/cadence_lifecycle/adapter.py`: blocked AEL/RUL adapters and fail-closed mapping checks. `io.py` provides write-once Parquet runs and manifests; `hazus.py` inspects/exports consequence partitions.
- Eight tests in `tests/test_{replacement,cashflows,consequences,adapter}.py` passed during the audit with bytecode/cache writes disabled. They cover basic scheduling/residuals, zero-discount NPC, consequence integration, and blocked mappings/adapters. They do not establish production equivalence or component-report coverage.
- `scripts/run_lifecycle_pilot.py` and `scripts/run_disposal_npv_pilot.py` have working CSV outputs. Lifecycle installation prices are **synthetic constant-2026-dollar inputs**, not observed roofing prices. The disposal pilot uses hard-coded illustrative events rather than joining generated events. `run_reference_cost_pilot.py` reads shared rates and rejects conflicting county rates.

### CADENCE functionality to reuse

Paths below are relative to sibling `../CADENCE/`:

| Code | Existing responsibility |
| --- | --- |
| `src/cadence/economics/alternative_analysis.py` | Scenario aging, replacement events, removed materials, annual cost comparison, cumulative discounted NPV |
| `src/cadence/economics/externalities.py` | Removal-event disposal/carbon; state → region → national tipping-fee fallback; expected downtime days × county daily relocation cost |
| `src/cadence/economics/materials.py`, `labor.py`, `costs.py` | Mapped mass/service lives, material and labor calculations, installed costs and provenance |
| `src/cadence/economics/alternative_pipeline.py`, `reporting.py` | Alternative-analysis orchestration and report outputs |
| `src/cadence/vulnerability/annual_damage.py`, `expected_damage.py` | Annual climate-scaled, age-specific damage and existing return-period/AEP integration |

Relevant upstream tests include `test_economics_externalities.py`, `test_economics_materials.py`, `test_economics_costs.py`, `test_alternative_analysis.py`, and `test_alternative_pipeline.py`. These were identified but not executed in the audit. Reuse interfaces and validated calculations rather than creating a second stock-flow engine. Current architecture uses explicit data boundaries without runtime imports from CADENCE.

## Shared references and pilot anchors

Paths below are relative to `../cadence_shared_data/reference_data/`:

| File | Audited contents |
| --- | --- |
| `disposal/EREF_2024_Tipping_Fees_Parsed.csv` | 51 geographic fee rows; EREF 2024; North Carolina **$39.71 per short ton** |
| `loss_of_use/temporary_housing_relocation_costs.csv` | 4,764 observations, source year 2025; Durham County FIPS **37063**, two-bedroom relocation **$62.40/day** |
| `material_mass/roofing_lbs.csv` | Seven classes; pounds per roofing square/per square foot, typical service life, source references |

Keep source years distinct from the financial dollar base; labeling an input “2026 real” does not establish an inflation conversion. Preserve source geography, bedroom assumptions, mapping approvals, and units (100 square feet per roofing square; 2,000 pounds per short ton).

Housing has 3,228 county identifiers: 66 have multiple observations and 18 have differing daily rates. CADENCE currently uses `.unique("county_fips")`; an explicit deterministic selection or approved aggregation policy is needed. Reject unresolved ambiguity rather than selecting an arbitrary row. CADENCE's configured disposal/housing `Data/` paths are absent in the inspected checkout; expose read-only source paths instead of copying data into siblings.

## Overlap and unresolved modeling differences

- **Overlap:** discounting, baseline subtraction, replacement schedules, disposal arithmetic, and downtime monetization exist in both development paths. Reuse CADENCE contracts and the lifecycle cash-flow machinery instead of adding parallel implementations.
- **Financial reconciliation:** lifecycle includes terminal service credit; CADENCE alternative analysis does not currently use the same convention. Align horizon endpoints, operating/event timing, eligible terminal basis, and dollar years before comparing totals.
- **Hazard integration:** lifecycle accepts probability masses summing to one. CADENCE integrates RP10–RP500 damage ratios with trapezoidal AEP segments and provisional endpoints `(1, 0)` and `(0, 1)`. Its ratio-bounded routine cannot simply be applied to downtime days or debris mass. Reuse audited annual consequences or a verified measure-specific adapter.
- **Repair valuation:** CADENCE uses installed roofing cost × expected damage ratio; lifecycle accepts building/contents exposure values. Resolve what each curve represents before selecting a cost basis.
- **State and mapping:** fixed-EUL schedules remain illustrative. Verify production RUL/degradation and burnout/upgrade precedence. CADENCE flags/caps vulnerability lookup ages at 30; the lifecycle contract prohibits unsupported extrapolation, but its production age-validation adapter remains unimplemented. Existing upstream proxies are not automatically approved for every lifecycle consequence measure.
- **Cost scope:** separate routine roof removal from hazard debris cleanup and check installation/repair coverage of disposal and displacement. Maintenance, salvage, and casualty effects require explicit sourced inputs or disabled status. Preserve combined installed-cost overrides where a defensible material/labor split is unavailable.
- **Documentation status:** the older `architecture.md` statement that CADENCE was inaccessible is superseded by this local audit. Compatibility, attribution, and policy approval remain unresolved; source inspection is not regression validation.

## Prioritized integration roadmap

1. **Approve property-damage and loss-of-use scope.** Resolve timing, terminal convention, repair basis, geographic selection, and stream boundaries. Identify supported non-roof building/contents consequences and exposure values through the existing research layer. Verify how a roof upgrade changes those losses and prevent overlap with roof repair/replacement. Keep community-level FEMA property-risk estimates separate from attributable asset-level benefits until a defensible method is established.
2. **Adapt existing inputs.** Define CADENCE-shaped event/state/cost interfaces and configurable read-only source paths. Preserve mapping versions, source hashes, financial conventions, and completeness. Keep CADENCE responsible for production state.
3. **Connect disposal and loss of use.** Replace hard-coded pilot events with generated removal events, track removed material across replacements, and reuse mass/fee logic. Monetize supported HAZUS expected downtime with deterministically selected housing rates; do not invent a new hazard-integration policy.
4. **Build the contribution report.** For each asset, decision year, option, and component, report baseline PV, option PV, contribution, source, and completeness. Use `contribution = baseline_component_PV - option_component_PV`; positive favors the upgrade. Represent terminal value as a signed cost credit so all contributions sum to `baseline_NPC - option_NPC`. Keep unsupported casualty attribution outside the decision total. Export an auditable table before visualization.
5. **Validate and prepare integration.** Test nonzero discounting, horizon boundaries, remaining-life/maintenance inputs, changed removed materials, geography ambiguity, missing versus disabled streams, and double-counting boundaries. Reconcile component sums to total NPV and compare equivalent inputs against CADENCE with explicit terminal-policy adjustments. Preserve uncertainty and sensitivity results. Propose production integration only after reconciliation and approval.

## Approved implementation progress

Following user approval, the component-reporting and generated-disposal-event implementation is authorized on `feature/cost-driver-analysis`. It retains lifecycle discounting, baseline comparisons, and terminal credits, and delegates disposal pricing to unmodified CADENCE source through an opt-in read-only subprocess bridge. See [report contracts and reproduction](cost_driver_report.md).

The mapping CSVs required for CADENCE official-class consolidation are absent from the current workspace. The pilot therefore uses exact shared-source material subtypes; the approved-mapping adapter fails closed when its files are missing. No mapping or physical service-life policy is invented. Existing financial/EUL pilot assumptions remain explicitly illustrative.

The next modeling priorities are property damage beyond the roof, contents damage, and loss of use. [Casualty-risk research](casualty_research_plan.md) is deferred. Community baseline risk stays outside attributable upgrade benefits until the evidence and method are approved. The user has authorized committing and pushing this repository's reviewed changes on `feature/cost-driver-analysis`; sibling repositories remain read-only.
