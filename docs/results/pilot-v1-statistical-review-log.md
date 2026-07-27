# Pilot v1 Statistical Review Log

Date: 2026-07-27  
Status: Four-round review complete

## Round 1: Mathematical and Statistical Review

- Resampling is paired at the complete-question level.
- Every interval uses 10,000 resamples, seed `20260723`, and the percentile
  95% confidence interval.
- Binary path and policy comparisons use the exact McNemar test based on the
  two discordant cell counts.
- P-values are Holm-adjusted within each declared path, stage, or router
  comparison family.
- The reported effect is always the first method's mean minus the second
  method's mean. Positive harmful-expansion differences therefore indicate
  more harm, whereas positive completeness and combined-success differences
  indicate improvement.

## Round 2: Data-Handling Review

- Pooled comparisons contain 120 paired questions.
- Domain-specific comparisons contain 60 paired questions per domain.
- No question is resampled or compared independently across paths.
- No missing question-path outcome is silently dropped.
- Construction categories and annotation labels are not model inputs.
- Outer-test predictions are not used for model fitting, scaling, calibration,
  or threshold selection.

## Round 3: Per-Table Review

- Each binary comparison contains an observed percentage-point difference, a
  paired 95% confidence interval, both discordant counts, an exact p-value, and
  a Holm-adjusted p-value.
- Path tables report evidence completeness, harmful expansion, and combined
  success separately.
- Selective results report all-question and accepted-decision denominators
  separately.
- Zero-coverage folds and models retain `null` accepted risk rather than
  imputing a favorable value.

## Round 4: Cross-Table Review

- The pooled P2-minus-P0 combined-success difference equals the
  context-stage P2-minus-P0 difference.
- Router-versus-heuristic differences equal the corresponding pooled
  no-abstention success-rate differences in the OOF manifest.
- The quantitative signal manifest retains the same 23/120 Signal 1 numerator,
  module rescue counts, and two-of-five final signal count.
- No confidence interval or significance result is used to override a frozen
  Go/No-Go threshold.

## Review Outcome

The statistical implementation is suitable for the amended diagnostic
manuscript. Remaining work is descriptive category analysis, cross-domain
transfer, publication tables and figures, and manuscript drafting.

