# Pilot v1 Publication Tables

The CSV files in this directory are generated only from tracked aggregate
manifests. Percentages are reported on a 0--100 scale. Blank cells indicate
that a metric is not defined for that policy.

- Table 1: Dataset and annotation summary.
- Table 2: P0--P5 path outcomes, pooled and by domain.
- Table 3: Matched stage effects with paired 95% intervals and exact tests.
- Table 4: Baseline, learned-router, and Oracle policy results.
- Table 5: Descriptive two-direction transfer results.
- Table 6: Frozen Go/No-Go signals.

Notes:

- Positive differences in Table 3 favor the first path for combined success.
- Holm adjustment is applied within the five stage comparisons.
- Oracle neural calls use routable questions only and are not directly
  deployable.
- Transfer results are descriptive because domain and language shift together.
