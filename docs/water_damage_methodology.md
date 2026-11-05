# Roof-entry, interior and contents methodology

Status: functioning **provisional research implementation**, not a calibrated
CADENCE predictive model. The reference is Roberto Vicente Silva de Abreu (2019),
*Modeling of Hurricane-Induced Interior and Contents Damage and Associated
Time-Related Expenses to Residential Buildings*, Florida Institute of Technology,
[thesis landing/download](https://repository.fit.edu/cgi/viewcontent.cgi?article=2083&context=etd).
The website returned 403; the user supplied the original 94-page PDF on November
4, 2026. Chapters 2–5 and Appendix A were inspected from extracted text; equations
2/3 were additionally checked visually on printed page 42 (PDF page 55).
The PDF remains outside Git. Extracted text/screenshots are ignored local research
artifacts, not redistributable project source datasets.

Related primary publication: Silva de Abreu, Pinelli, Raji and Zisis (2020),
[Journal of Wind Engineering and Industrial Aerodynamics 207, 104427](https://doi.org/10.1016/j.jweia.2020.104427).
The publication identity and methodological lineage are corroborated by the
[FPHLM research group](https://fphlm.cs.fiu.edu/publications.html); the implementation
uses the supplied thesis, not coefficients inferred from an inaccessible article.

## Published relationships and limitations

The thesis separates interior components (ceilings, partitions, flooring, cabinets,
electrical) from contents. Chapter 3 uses six compartments with experimental
direction-dependent distribution tables. Water first reaches ceilings through roof
openings, then excess propagates through partitions, contents and floor (pp39–42).
Its absorption capacities, direction generalizations, cabinet/electrical weights
and propagation order include engineering assumptions, not universal constants.

On p42, with `x = WCT/WAC`, the printed equations are:

* Interior: `d_i(x) = x^5 / 2 + 0.6785 x` (equation 2).
* Contents: `d_c(x) = sin(x)^1.5 / 2 + x^20` (equation 3, sine in radians).
* Cabinets: `0.6 d_floor + 0.4 d_partitions`.
* Electrical: `0.4 d_ceiling + 0.6 d_partitions`.

These expressions can exceed one near saturation (`d_i(1)=1.1785`,
`d_c(1)≈1.386`). This implementation explicitly bounds `x` and damage to `[0,1]`.
That bound is an implementation safeguard, not an unmentioned alteration of the
printed equations. Curves are zero at zero, monotone on the supported interval,
and applied to retained water divided by the supplied absorption capacity.

Printed pp44–48, equations 4–8 combine opening area, rain admittance, surface runoff,
storm rotation shares, height correction and accumulated rain, then distribute the
resulting volume among interior components. This implementation retains the
area-times-rain dimensional relationship but does **not** reproduce all these
terms, six-cell geometry, or the thesis's complete FPHLM Monte Carlo model.

Chapter 3 cites a 30% gypsum mass absorption assumption (p29) and contents capacity
five times floor absorption (p30), both requiring further calibration. These are
not installed as hidden defaults. Section 5.2 (pp73–74) calls for more experiments,
capacity/propagation testing, probabilistic treatment, and calibration/validation.

## Explicit reduced-order adaptation

One caller-defined wetted footprint represents one single-story residential roof
path. This is suitable for sensitivity and adapter testing; it excludes windows,
doors, wind pressure, runoff collection, hidden leaks, horizontal transport,
drying, multistory transport and storm surge. Geometry/roof archetype mappings and
wind-to-breach/rain calculations stay upstream. In particular a monetary roof
damage ratio cannot be substituted for a physical opening fraction.

`A_eff = A_roof [b + (1-b) c k]` in m², where `b` is supplied deck breach
fraction, `c` is supplied covering-loss fraction on the intact-deck remainder, and
`k` is a scenario penetration fraction through that exposed deck/underlayment.
`V = A_eff R eta` in liters, with accumulated effective incident roof rain `R`
in mm and supplied entry efficiency `eta`. Because `1 mm*m²=1 L`, no hidden rain
unit conversion occurs. `k` and `eta` are assumed unless separately calibrated.
The paths are disjoint, hence `A_eff <= A_roof`. Runoff amplification is excluded.

For each component `j` in ceiling → partitions → contents → floor:

`C_j = A_wet q_j`; `retained_j = min(incoming_j, C_j)`;
`overflow_j = incoming_j - retained_j`; `x_j = retained_j/C_j`.

Capacity density `q_j` is L per m² of **wetted footprint**. Wall capacities derived
per m² of wall must first be converted using actual wall/footprint area. Ground
floor excess is reported as ponded water. At every event,
`sum(retained_j) + ponded = V`; water volume is never independently charged to
multiple reservoirs. Contents damage uses its retained water, not interior dollars.
Interior dollars sum the five distinct interior values times their damage ratios.
Contents dollars equal exposed contents value times its own damage ratio.

Exposed values are caller-supplied **replacement values within the footprint**;
do not pass full-house values for a partial footprint without a defensible spatial
allocation. No arbitrary contents/interior dollar multiplier is used. The example
sets an explicit contents inventory value and varies it in sensitivity; there is
no claimed nationally representative default contents value.

## Hazard integration and overlap

Event losses are undiscounted conditional losses. Production annualization,
rain/breach joint distributions, roof states, climate and event frequency are
upstream responsibilities. For the demonstration only, supplied, mutually
exclusive synthetic annual-maximum event masses are passed to the existing
`integrate_discrete_hazard` function. A no-storm mass is included. This is not a
Poisson multistorm model, nor a return-period/AEP conversion. Neither nonlinear
damage functions nor event water balances may be evaluated at mean annual water
and represented as expected damage; integrate conditional losses instead.

Thesis section 2.3 (p6) confirms that HAZUS hurricane building losses already
contain interior water effects and a separate contents channel. New interior and
contents therefore either **replace** those channels or use explicitly isolated
roof/exterior-only upstream costs. Total HAZUS building loss plus this interior
model is rejected by the analysis scope contract. Loss of use remains a separate
supplied annual displacement-days/cost stream; no new downtime curves are inferred.

## Validation and uncertainty

Tests independently check a known area/rain volume; mass conservation; the printed
equation midpoint; zero exposure; monotonic response; damage/exposed-value bounds;
disjoint opening paths; and invalid/missing inputs. These verify implementation,
not predictive accuracy. No independent storm inventory or measured loss dataset
is available for calibration. Low/central/high example scenarios vary rain,
breaches, capacities, contents values, downtime, EUL, maintenance and discounting;
rank changes reflect those assumptions, not estimated confidence intervals.
