# Deferred research specification: FEMA casualty risk

Status: deferred following the user's November 2, 2026 clarification. Property damage beyond the roof, contents damage, and loss of use are the next priorities. This earlier research specification is retained for context; it does not authorize casualty-risk implementation. No FEMA casualty inputs, allocation factors, or avoided-casualty benefits have been added to the current NPV calculation. A disabled or excluded benefit is not evidence of zero underlying casualty risk.

## Research question and ownership

Determine whether FEMA National Risk Index estimates can support a defensible estimate of changes in residential occupant casualty losses caused by a particular roof upgrade under the modeled hazards. Community-level baseline risk alone does not establish that an individual roof upgrade avoids any specified fraction of those losses.

Use the Economic Externalities Research Database as the source-data research layer. First inventory its existing products and methodology; do not create another download/extraction pipeline in lifecycle economics. Sibling research repositories remain read-only under current authorization. Lifecycle work should consume an approved, versioned research product through an explicit contract.

## Evidence needed before implementation

1. **Source identity and definitions.** Obtain the intended official FEMA release, technical methodology, data dictionary, license/use conditions, download identity and checksum. Verify the meaning of casualty-related fields, whether they represent counts, monetized annual losses, or indices/scores, and any distinctions among fatalities/injuries. Do not treat a relative risk score as dollars or monetize an already monetized field again.
2. **Hazard and geography match.** Identify supported hazard-specific estimates, source geography/vintage, FIPS and population/exposure denominators, missing/suppressed observations, and uncertainty. Match the modeled roof-relevant hazard and residential exposure. Do not assign an all-hazard community aggregate directly to a single roof.
3. **Attribution evidence.** Establish which casualty mechanisms can be affected by roofing, and obtain empirical or otherwise justified relationships between hazard intensity, roof performance/failure, occupancy, and casualty outcomes. Separate roof-mediated effects from other building, environmental, and behavioral causes. Roof damage reduction alone is not a validated casualty-reduction factor.
4. **Asset allocation and counterfactual.** Specify whose risk is valued (occupants/household versus community), the exposure denominator, and the allocation model. Explain how asset-level estimates aggregate consistently without assigning the same community risk to multiple assets. Hold exposure assumptions consistent between keep-until-burnout and upgrade scenarios. An unsupported equal-per-building allocation is not an approved default.
5. **Climate and financial alignment.** Reconcile the baseline hazard period and annualization with CADENCE's climate trajectory and hazard integration. Any change to casualty estimates over time requires its own documented method; do not scale community losses by roofing damage ratios implicitly. Identify any valuation policy, source/base year, inflation adjustment, annual timing, and discount convention without inventing valuation constants.
6. **Overlap and uncertainty.** Check overlap with source casualty valuation, repair/building loss, contents, displacement, and other externalities. Identify uncertain attribution, occupancy, effectiveness, exposure, and valuation parameters; specify sensitivity ranges supported by evidence and structural alternatives, including a baseline-only case.

## Proposed data boundary

Keep two separate research products:

- A **community baseline-risk table**, keyed by geography, hazard, source release and baseline period, carrying measure definition/unit, exposure denominator, source dollar year where relevant, missingness, and uncertainty. It is contextual baseline risk, not a roof-upgrade benefit.
- An **approved attribution specification/table**, identifying asset/roof scenario applicability, evidence references, exposure allocation, hazard conditioning, causal assumptions, model version, uncertainty bounds, approval status, and invalid-use cases. No implicit attribution coefficient is allowed.

Only after approval should an adapter produce annual baseline and option casualty costs at the existing lifecycle cash-flow grain. Compute the incremental contribution through the same reporting/discounting path as other components. A scenario-independent baseline cancels in an incremental comparison; it must not be relabeled as avoided loss. Until attributable differences are supported, keep baseline risk visible in a separate contextual output and exclude it from upgrade NPV.

## Acceptance gates

- Review source-field interpretation and valuation with explicit citations to the selected official documentation; this research has not yet been completed.
- Approve the causal and allocation method, geographic/hazard scope, climate treatment, and uncertainty representation before adding a casualty stream to the decision total.
- Validate units, FIPS retention, missing-versus-zero status, no double monetization, population/exposure accounting, and no duplicate casualty attribution across assets.
- Demonstrate zero incremental casualty benefit when scenario risks are identical, correct baseline subtraction when attributable risks differ, and reconciliation to total NPV under the existing timing conventions.
- Publish source/version hashes, assumptions, sensitivity results, and limitations in a reviewable research artifact before production integration.

This work is deferred behind the property-damage and loss-of-use priorities. Completing the present component report does not resolve casualty attribution or authorize edits to the source research repositories.
