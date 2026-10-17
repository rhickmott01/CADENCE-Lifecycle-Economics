# Validation and acceptance

1. Fixed-EUL replacement dates: 8 years RUL and 20 EUL -> offsets 8 and 28 in 30 periods.
2. Immediate replacement offset 0; no duplicate terminal-boundary event.
3. Terminal residual: new roof with 18 years left and $20k cost -> $18k at boundary.
4. If original roof remains, use existing-roof cost basis, not candidate material price.
5. Zero discount: NPC matches arithmetic sum of costs minus terminal credit.
6. Missing annual stream rows are errors, not zeros.
7. Discrete hazard weights sum to 1; curve support complete; no return-period-to-probability invention.
8. Building/content loss ratio in [0,1]; downtime and debris nonnegative.
9. Unapproved HAZUS proxy rejected; age >30 rejected by future adapter.
10. No writes to existing versioned output directory.
11. After actual CADENCE source audit: match existing AEL and existing economics under equivalent inputs and disabled new streams.
12. Benchmark 100, 1,000 and 10,000 assets after dependencies and real data become available.

Run `pytest -q` after installing `.[dev]`.
