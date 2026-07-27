# Diagnostic Evidence-Path Study Design

Date: 2026-07-27  
Status: Approved and frozen for manuscript completion  
Repository: `calibrated-regulatory-evidence-routing`

## 1. Approved Title and Positioning

English title:

> When Does Evidence Expansion Help? A Cross-Domain Study of Retrieval
> Paths and Lightweight Routing for Regulatory Evidence

Chinese title:

> 证据扩展何时有效？监管证据检索路径与轻量路由的跨领域实证研究

The paper is an empirical and diagnostic study, not a claim that calibrated
evidence routing has been solved. It analyzes when reranking, context
augmentation, and bounded graph traversal improve regulatory evidence
retrieval, when they add harmful evidence, and what a small-sample lightweight
router can and cannot predict.

## 2. Reason for the Amendment

The frozen 120-question Pilot passed two of five preregistered quantitative
signals. Oracle routing and learned no-abstention routing passed, while the
minimum routing-need fraction, independently useful module count, and
calibrated-abstention requirements did not pass. The original protocol
therefore prohibits expansion into a larger routing dataset.

This amendment preserves every frozen question, path, annotation, threshold,
split, and reported negative result. It changes only the manuscript claim and
the authorized next-work boundary.

## 3. Research Questions

1. How do six frozen evidence paths differ in evidence completeness, harmful
   expansion, combined success, and cost across two regulatory domains?
2. Which path stages independently rescue failed retrievals, and which stages
   primarily add cost or harmful evidence?
3. Can Logistic Regression or XGBoost select more successful paths than a
   frozen cue-based heuristic under grouped out-of-fold evaluation?
4. Do calibration-only thresholds support useful evidence-sufficiency
   abstention, and what failure modes arise when they do not?
5. Which findings are shared across the chemical and pharmaceutical domains,
   and which are domain-specific?

## 4. Contributions

The manuscript may claim four contributions:

1. A risk-sensitive two-domain Pilot containing 120 questions, 720
   question-path outputs, evidence completeness specifications, harmful
   evidence labels, duplicate annotation, and adjudication.
2. A controlled six-path comparison that separates completeness, harmful
   expansion, combined success, and execution cost.
3. An attributable stage analysis showing that context augmentation provides
   the strongest independent benefit in this Pilot, while reranking and graph
   traversal provide sparse incremental rescue.
4. A leakage-safe comparison showing that lightweight learned routing
   outperforms a frozen heuristic in no-abstention mode, while preregistered
   calibrated abstention does not achieve acceptable risk and coverage.

The manuscript must not claim a new state-of-the-art router, reliable
cross-lingual generalization, guaranteed regulatory answer correctness, or
successful calibrated abstention.

## 5. Frozen Data and Methods

The study retains:

- 60 Chinese chemical-safety questions and 60 English pharmaceutical
  regulatory questions;
- the six frozen paths P0 through P5;
- BM25, the frozen reranker, parent/heading/table-text context, and one-hop
  `CITES`/`DEPENDS_ON` traversal;
- `REQUIRED`, `SUFFICIENT`, `CONTEXT`, `IRRELEVANT`, and `HARMFUL` labels;
- document-grouped five-fold evaluation;
- Logistic Regression, XGBoost, BM25-only, all-modules, frozen heuristic, and
  Oracle policies;
- the calibration-only threshold procedure and its negative result.

No additional questions, labels, paths, models, or hyperparameter searches are
authorized.

## 6. Remaining Analyses

The final analysis must report:

- pooled and per-domain P0-P5 outcomes;
- matched stage-rescue counts for reranking, context, and graph traversal;
- pooled and fold-level learned-router comparisons against the heuristic;
- coverage, accepted risk, abstention rate, Brier score, and frozen-bin ECE;
- descriptive chemical-to-pharmaceutical and pharmaceutical-to-chemical
  transfer;
- 10,000 paired question-level bootstrap intervals with seed `20260723`;
- construction-category diagnostics used only to inspect authoring artifacts,
  never as router inputs;
- annotation agreement and adjudication statistics;
- all five preregistered Go/No-Go signals, including failures.

## 7. Manuscript Structure

1. Introduction
2. Related Work
3. Study Design and Regulatory Corpora
4. Evidence Paths, Annotation, and Lightweight Routing
5. Experimental Setup
6. Results
7. Discussion and Limitations
8. Conclusion

The Results section leads with path-level evidence findings, then stage
attribution, learned routing, calibration failure, and transfer diagnostics.
The failed expansion gate appears as a scientific finding rather than an
implementation error.

## 8. Output Boundary

The final manuscript will be delivered as an editable English `.docx` file.
Intermediate Markdown, JSON, CSV, and image artifacts may be generated for
reproducibility. A PDF is permitted only as a temporary rendering artifact for
visual quality assurance and will not be the user-facing final deliverable.

## 9. Exclusions

- no full-dataset expansion;
- no multimodal table-image or cell-level retrieval;
- no Transformer router, Agent workflow, or multi-hop reasoning;
- no generated-answer or claim-verification study;
- no post hoc threshold relaxation;
- no test-set threshold selection;
- no omission of failed preregistered signals.

## 10. Completion Criteria

The amended study is complete only when:

- all remaining statistics and confidence intervals reproduce from frozen
  private inputs;
- the feasibility report records the original `NO-GO` expansion result;
- manuscript tables and figures are generated from tracked analysis outputs;
- citations are verified;
- the final English Word manuscript passes content and visual review;
- the repository passes tests, formatting, and privacy scanning.

