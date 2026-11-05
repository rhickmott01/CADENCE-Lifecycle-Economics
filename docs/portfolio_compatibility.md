# Portfolio integration audit — November 4, 2026

The user-designated [Portfolio Mapping repository](https://github.com/Ajjme/CADENCE_Portfilio_Mapping)
was inspected through authenticated, read-only GitHub API requests at tree
`0392d17dbacc9076174850dc2cdcbc0f0bc049d5`. Selected source snapshots and the
full file inventory are local, ignored research artifacts in `outputs/research/`.
This is an audit of source, not a certification of a running dashboard.

## Verified boundaries

The root README describes a Streamlit portfolio/Alternative Analysis dashboard.
Its embedded `CADENCE/` contains economics, vulnerability, insurance, program,
reference-data, and UI modules. No separately authoritative multi-repository
exchange specification was found among its README, economics/program/Streamlit
documentation, connectivity review, material rules, or inspected contracts.
Consequently the new lifecycle exchange is explicitly **proposed version 1**.

| Producer / consumer | Verified convention / lifecycle boundary |
| --- | --- |
| Asset preprocessing | `asset_id`, five-character `county_fips`, state, ZIP/CBSA, roof area; geometry is unnecessary for economic calculation |
| Research / reference layer | Prices, wages, mass, tipping fees, housing, mappings; consume processed outputs, preserve hashes, do not extract raw research again |
| Vulnerability | Climate, terrain, wind grid, RP10/25/50/100/200/500 gusts, age/material-specific response; remains upstream |
| Economics | Annual price grain `(asset_id, year, official_material_id)`; combined installed costs retain their basis without an invented labor split |
| Alternative analysis | `(asset_id, year, scenario_id)`; `BASELINE_CURRENT`, `NEW_ASPHALT`, `NEW_METAL`, `NEW_TILE`; automatic in-kind replacement |
| Lifecycle exchange | Keep upstream scenario IDs; add independent `assumption_set_id` for sensitivity, `option_id`, decision year, component and provenance |
| Dashboard | DuckDB reads Parquet summaries/annual partitions; joins asset geometry separately for mapping |
| Program / stock-flow | Upstream owns state, installation decisions, adoption and burnout precedence; lifecycle results are analytical inputs only |

Parquet is verified for analytical exchange; GeoParquet is not required for these
geometry-free tables. New results do not masquerade as the dashboard's existing
`v0.4.0` results: they need an explicit downstream adapter and approval.

## Differences requiring reconciliation

* Upstream contracts lock 2026–2050 inclusive (25 periods), default 2% real;
  lifecycle permits a configurable horizon and rate. Its existing 30-year pilot
  uses offsets 0–29 and a terminal credit at 30. Both use start-of-period costs.
* Upstream alternative analysis has no matching straight-line terminal credit.
  Compare totals only with a common horizon and terminal policy.
* Approved official IDs are `OFFICIAL_ASPHALT/METAL/TILE`. Local shared mass uses
  exact source subtypes. No implicit subtype-to-official mapping is introduced.
  A caller supplies an explicit, sourced option/scenario crosswalk.
* Upstream integrates bounded damage ratios over AEP with provisional endpoints
  `(1,0)` and `(0,1)`. Lifecycle's discrete-mass function accepts **already formed**
  mutually exclusive masses; it does not turn return periods into probabilities.
  These methods are not declared equivalent. Annualization stays upstream.
* Upstream repair is installed-roof value times damage ratio. HAZUS total building
  losses can already include water-related interior damage; they must not be
  added to separate interior estimates. A roof/exterior-only scope declaration
  and a documented extraction/replacement method are required by the new adapter.
* Portfolio documentation calls housing/disposal fixed 2026-real proxies, while
  shared sources are 2025/2024. The new demonstration uses 2024 real dollars and
  explicit **illustrative** housing conversion; no observed inflation is claimed.
* The connectivity review documents disconnected annual downtime, partial totals,
  and cache/source-identity gaps. Some prose is stale (economics documentation
  both describes NPV and later says it is unimplemented; climate prose similarly
  conflicts). Executable source governs the audit of current behavior.

Local CADENCE source inspected: `economics/{contracts,externalities,materials,
alternative_analysis}.py` and `vulnerability/expected_damage.py`. Its files and all
shared/research repositories are read-only throughout this assignment.

## Reference anchors rechecked

Shared CSVs confirm NC EREF 2024 tipping fee **39.71 USD/short ton**, Durham FIPS
`37063` 2025 two-bedroom housing **62.40 USD/day**, and architectural asphalt mass
**2.5 lb/ft²**. Roofing square = 100 ft², short ton = 2,000 lb. Identical duplicate
housing rates collapse deterministically; conflicting county/year/bedroom rates
are rejected. These source values alone do not establish a common dollar year.
