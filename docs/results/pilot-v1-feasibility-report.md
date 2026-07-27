# Pilot v1 Feasibility Report

**Study:** Calibrated evidence routing for cross-domain regulatory retrieval  
**Pilot size:** 120 questions and 720 frozen question-path outputs  
**Decision date:** 2026-07-27  
**Expansion decision:** **NO-GO**  
**Approved disposition:** Complete a narrower diagnostic manuscript without
expanding the dataset

## Executive Result

The Pilot did not satisfy the preregistered continuation rule for expanding
the calibrated-routing study. Two of five quantitative signals passed, whereas
the frozen protocol required at least four. The result was not repaired by
changing thresholds, adding paths, tuning on outer-test predictions, or
removing difficult questions. The data nevertheless support a narrower
empirical study of evidence-path utility. Context augmentation produced a
clear, repeatable increase in complete and risk-aware retrieval, and both
lightweight learned routers selected successful paths more often than the
frozen cue-based heuristic. Reranking and graph traversal provided little
independent rescue, and calibration-based abstention did not attain useful
coverage at acceptable risk.

The original large-scale routing claim is therefore discontinued. The
approved manuscript will instead ask when evidence expansion helps, where it
introduces harmful material, and which limits appear when lightweight routing
and abstention are evaluated across two regulatory domains.

## Frozen Study Record

The Pilot contained 60 Chinese chemical-safety questions and 60 English
pharmaceutical-regulation questions. Each question was processed through six
frozen evidence paths, yielding 720 question-path outputs. The final
annotation freeze contained 10,385 evidence-label occurrences, including
1,232 `HARMFUL` labels. Thirty complete questions received independent
duplicate annotation. Exact duplicate agreement was 71.48% (95% cluster
bootstrap interval, 66.11%–76.85%), and Cohen's kappa was 0.556 (95%
interval, 0.470–0.637). All 279 queued disagreements and harmful-reason
differences were adjudicated, corresponding to 837 final path-level label
occurrences. Twenty-seven corpus searches documented questions for which
complete evidence was unavailable in the frozen corpus.

The agreement statistics indicate moderate rather than near-perfect
reliability. The ordered harmful-evidence criteria, complete-question duplicate
unit, retained raw labels, and adjudication record nevertheless provide a
transparent operational distinction among complete evidence, retrieval
failure, harmful expansion, and corpus insufficiency.

## Evidence-Path Outcomes

Table 1 summarizes the pooled outcomes. P0, the BM25-only baseline, achieved
complete evidence on 26.67% of questions and combined path success on 17.50%.
P2, which added context to BM25 seeds without a neural call, increased
completeness to 55.00% and combined success to 33.33%. P5 reached the highest
completeness, 63.33%, but its harmful-expansion rate was also high at 51.67%;
its combined success therefore remained 33.33%, equal to P2. The result
illustrates why completeness alone is insufficient for regulatory evidence
retrieval.

| Path | Completeness | Harmful expansion | Combined success | Mean neural calls |
|---|---:|---:|---:|---:|
| P0 | 26.67% | 40.83% | 17.50% | 0.00 |
| P1 | 34.17% | 50.00% | 19.17% | 1.00 |
| P2 | 55.00% | 42.50% | 33.33% | 0.00 |
| P3 | 28.33% | 40.83% | 18.33% | 0.00 |
| P4 | 61.67% | 51.67% | 32.50% | 1.00 |
| P5 | 63.33% | 51.67% | 33.33% | 1.00 |

![Pooled path outcomes](../../artifacts/pilot-v1/figures/figure1_path_outcomes.png)

## Attributable Stage Effects

Matched comparisons isolated the effect of each added stage. Adding context
through P2 rather than P0 improved combined success by 15.83 percentage points
(95% paired bootstrap interval, 9.17–22.50 points; Holm-adjusted exact
McNemar *p* < 0.001). Context after reranking, P4 rather than P1, improved
combined success by 13.33 points (95% interval, 7.50–20.00 points;
Holm-adjusted *p* < 0.001). Reranking alone improved combined success by only
1.67 points, with an interval spanning zero. Each graph comparison improved
combined success by 0.83 points, with intervals beginning at zero.

The rescue-count analysis led to the same conclusion. Reranking independently
rescued three questions, context rescued 19, and graph traversal rescued one.
Only context met the frozen requirement of at least five unique rescues.
Construction-category analysis showed that context rescue was concentrated in
parent/heading and table-related questions, particularly in the pharmaceutical
domain. This concentration is substantively plausible, but it also means the
effect should not be presented as uniformly domain-independent.

![Paired stage and router effects](../../artifacts/pilot-v1/figures/figure2_paired_effects.png)

## Lightweight Routing

The frozen heuristic achieved combined success on 19.17% of questions. In
grouped pooled out-of-fold evaluation, Logistic Regression achieved 32.50% in
no-abstention mode, an improvement of 13.33 percentage points (95% paired
bootstrap interval, 6.67–20.83 points; Holm-adjusted exact McNemar
*p* = 0.0017). XGBoost achieved 31.67%, an improvement of 12.50 points
(95% interval, 5.83–20.00 points; Holm-adjusted *p* = 0.0017). The improvement
was positive in four of five outer folds for both models.

These results support a limited claim: simple pre-execution features can
improve path selection relative to a frozen lexical heuristic. They do not
show that either learned router is reliably calibrated, that it generalizes
independently of domain and language, or that it approaches the Oracle. The
Oracle succeeded on 36.67% of all questions because only 44 of 120 questions
had any successful candidate path.

## Calibration and Abstention

The preregistered abstention criterion required at least 20% pooled coverage,
accepted failure risk no greater than 10%, and at least a five-point risk
reduction relative to the same router without abstention. Logistic Regression
accepted 11 of 120 outer-test decisions, producing 9.17% coverage and 63.64%
accepted failure risk. Four of five folds forced full abstention because the
calibration partition contained no valid operating threshold. XGBoost forced
full abstention in all five folds and therefore had zero coverage.

The no-abstention Brier score and ten-bin expected calibration error were 0.200
and 0.098 for Logistic Regression, compared with 0.289 and 0.264 for XGBoost.
These global values do not rescue the selective policy: the accepted
outer-test decisions remained unreliable. Thresholds were not scanned or
replaced using test predictions.

## Cross-Domain Transfer

Cross-domain transfer was evaluated descriptively because the chemical domain
was Chinese and the pharmaceutical domain was English. Chemical-to-
pharmaceutical Logistic Regression achieved 45.00% no-abstention combined
success, whereas XGBoost achieved 30.00%. In the reverse direction, Logistic
Regression achieved 21.67% and XGBoost achieved 23.33%. Every source-domain
calibration procedure forced full abstention on its target domain.

These values cannot separate domain shift from language shift. They indicate
that learned path ranking may retain some signal across domains, but they
provide no evidence that calibrated abstention transfers.

## Qualitative Gates

The first qualitative gate passed. No single fixed route dominated both
quality and cost: P0 was cheapest but weak, P2 matched P5's combined success
without a neural call, and P5 increased completeness while also increasing
harmful expansion.

The second qualitative gate passed operationally. The annotation process
distinguished complete evidence, harmful expansion, retrieval failure, and
manually verified corpus insufficiency, although moderate inter-annotator
agreement remains a limitation.

The third qualitative gate did not pass conservatively. Path differences were
not reducible to a single explicit lexical cue, and construction categories
were excluded from model features, but the strongest context gains were
concentrated in authoring strata designed to require parent or table context.
The result is appropriate for a diagnostic study, but it does not support an
unqualified general routing claim.

## Quantitative Signals

| Signal | Frozen requirement | Observed result | Pass |
|---|---|---|:---:|
| 1 | At least 20% rescued beyond P0 | 23/120 = 19.17% | No |
| 2 | At least two modules rescue at least five questions each | Reranking 3; context 19; graph 1 | No |
| 3 | Oracle meets at least one practical improvement | All three Oracle alternatives met | Yes |
| 4 | A learned no-abstention router beats the heuristic | Both LR and XGBoost met the success condition | Yes |
| 5 | Coverage ≥20%, accepted risk ≤10%, and risk reduction ≥5 points | LR coverage 9.17% with 63.64% risk; XGBoost coverage 0% | No |

Only two of five quantitative signals passed. The required count was four.
Because both the quantitative requirement and one qualitative gate failed, the
final expansion decision is `NO-GO`.

## Interpretation and Approved Disposition

The `NO-GO` result applies to expansion of the original calibrated-routing
claim. It does not require discarding the completed Pilot. The evidence
supports a narrower paper centered on path utility, risk-sensitive evaluation,
and the limits of lightweight routing. The final manuscript will preserve the
positive context and router findings, present calibration and transfer failure
as boundary evidence, and avoid claims of reliable abstention or broad
cross-domain generalization.

No additional questions, labels, paths, models, or hyperparameter searches are
authorized. Multimodal table retrieval remains a separate future project and
is not part of this manuscript.

## Reproducibility Record

The aggregate values in this report are generated from the tracked manifests
for annotation freeze, path outcomes, paired uncertainty, pooled OOF routing,
construction diagnostics, transfer, and quantitative signals. Question-level
predictions, source passages, and completed annotation workbooks remain in
ignored private directories. The repository test suite, code-style check, and
privacy scanner must pass before manuscript release.

