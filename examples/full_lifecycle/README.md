# Reviewed illustrative lifecycle outputs

These are generated **synthetic research examples**, not production risk estimates.
All three physical roofing options run through all five economic pathways. Public
shared landfill/mass/housing reference anchors are used with explicit source years;
installed prices, damage, exposed values, physical capacities, maintenance, annual
event likelihoods and downtime are illustrative. The 2025 HUD rate is explicitly
held at a synthetic 2024 dollar proxy, not falsely labeled inflation-adjusted.
No raw thesis, private asset portfolio, research database or credentials is copied.

| Assumption set | Run directory |
| --- | --- |
| Low | `schema_version=lifecycle_exchange_v1/run_id=75b27427a7a30e234574cb42/` |
| Central | `schema_version=lifecycle_exchange_v1/run_id=051126e55fadfe434f81155f/` |
| High | `schema_version=lifecycle_exchange_v1/run_id=6361064100265fbdcb20a24b/` |

Each contains validated Parquet/CSV outputs, actual typed schemas, input/code
hashes, artifact checksums and standalone SVG/PNG contribution charts. Each also
contains the common 29-case sensitivity table: one central case, 20 one-at-a-time
endpoint cases for ten controls, and eight seeded joint draws. The low/central/high
sets vary assumptions together; they are not confidence bounds.

Reproduction, from repository root:

```sh
./.venv/bin/python -B scripts/run_full_lifecycle.py --sensitivity --samples 8 --seed 20261104 --output-root outputs/reproduction
```

The same inputs/code/library versions produce the same run identity in a fresh
root. A changed environment or code creates a new identity; compare the metadata.
Parquet is the machine-readable product; CSVs and charts are review aids. The
`source_year` and `base_dollar_year` fields are distinct. See the
[exchange contract](../../docs/lifecycle_exchange_v1.md) and
[implementation report](../../docs/full_implementation_report.md).
