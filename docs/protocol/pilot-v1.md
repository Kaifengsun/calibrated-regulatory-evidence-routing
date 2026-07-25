# Pilot v1 Frozen Execution Protocol

Date frozen: 2026-07-23

Status: frozen before Pilot path labels

This document is the human-readable companion to the machine-readable Pilot
configuration. If prose and configuration disagree, execution stops and the
protocol must be versioned before any Pilot output is inspected.

## 1. Frozen files

| File | SHA-256 |
|---|---|
| `configs/pilot-v1.yaml` | `bd405ca9561ea407f833e0ea48842a44fbedfa6160f00a747499d6b3450a0b40` |
| `configs/cues-v1.yaml` | `fa811d1fb4843bd950b2a9ddd5955cd25df5ae13ac82819b79a8d0b9897a995a` |
| `configs/reranker-v1.yaml` | `f8352e9e04ea9d2a91cb6e5d90f552321d5a5add67a36e33db7db06c9cffadd6` |

The Pilot seed is `20260723`. Configuration changes require a new protocol ID
and new hashes. Existing Pilot artifacts must never be silently relabeled as
belonging to the new protocol.

## 2. Dataset and split contract

The Pilot contains exactly 120 new questions: 60 Chinese chemical-safety
questions and 60 English pharmaceutical-regulatory questions. Each domain
contains exactly 12 questions in each of five construction categories:
direct clause, parent or heading context, table related, citation or dependency,
and evidence insufficient. Construction categories are excluded from router
features.

Questions from the same source document, standard, clause family, table, or
relation family share one `source_group_id`. Five-fold assignment uses a stable
hash under the Pilot seed. For outer fold `i`, fold `i` is test, fold
`(i + 1) mod 5` is calibration, and the remaining folds are training. The test
fold is unavailable to model fitting, probability calibration, and threshold
selection.

Cross-domain transfer is run in both directions. Model fitting, calibration,
threshold selection, and normalization use the source domain only. The complete
target domain remains untouched until evaluation.

## 3. Six evidence paths

BM25 is run once to depth 50. Ranked evaluation is truncated at 10.

| Path | Frozen execution |
|---|---|
| `P0` | BM25 top 10 |
| `P1` | BM25 top 50, neural reranking, top 10 |
| `P2` | BM25 top 10 plus context on the first five seeds |
| `P3` | BM25 top 10 plus graph expansion from the first five seeds |
| `P4` | BM25 top 50, reranking, then context on the first five reranked seeds |
| `P5` | BM25 top 50, reranking, context, then graph expansion from the same five seeds |

Context sidecars are ordered as heading path, immediate parent, and table, with
stable source ID as the final tie-break. No more than three sidecars attach to
one seed. They retain separate identifiers, do not occupy ranked positions, and
are evaluated separately.

Graph expansion follows one outgoing normalized `CITES` or `DEPENDS_ON`
relation. The first five seeds are preserved, no more than five unique graph
targets are inserted, and remaining positions are filled from the direct list.
The minimum confidence is 0.85.

For the pharmaceutical snapshot, explicit `REFERENCES` may normalize to
`CITES`. Explicit `REQUIRES_COMPLIANCE_WITH`,
`APPLIES_DEFINITION_FROM`, `USES_PRINCIPLES_FROM`, and `INTERPRETS` may
normalize to `DEPENDS_ON`. A relation is eligible only when it resolves
deterministically to one attributable text target; such a resolution receives
confidence 1.0. Ambiguous or non-textual targets are excluded. No relation is
inferred from generic multi-hop connectivity.

## 4. Frozen reranker

The reranker is `Qwen/Qwen3-Reranker-0.6B`, sourced from the ModelScope
`master` snapshot whose file-manifest SHA-256 is
`9e345ac4f295b7fe6f9734e1d5c1c73625b7a01ef2217be1896bb608c13fa508`.
The file manifest, rather than the mutable branch name alone, identifies the
immutable model state.

Inference uses bfloat16, maximum length 1,024, batch size 8, deterministic
algorithms, and normalized yes probability against no. Candidates are ordered
by reranker score descending, BM25 rank ascending, and stable source ID
ascending. The prompt and payload fields are stored verbatim in
`configs/reranker-v1.yaml`.

## 5. Evidence and annotation contract

Every evidence unit receives exactly one of `REQUIRED`, `SUFFICIENT`,
`CONTEXT`, `IRRELEVANT`, or `HARMFUL`. Complete evidence means that every
required identifier is present, or that a sufficient item satisfies a
single-item specification. One harmful ranked unit or eligible sidecar makes
combined path success zero even when evidence is complete.

Evidence completeness, harmful expansion rate, and combined path success are
reported separately. Six path failures never imply corpus insufficiency.
Corpus insufficiency requires a documented manual search of the frozen corpus
that finds no complete evidence.

Exactly 30 complete questions receive independent duplicate annotation,
stratified as three questions from each domain-category cell. Duplicate review
covers all six paths and all ranked and sidecar evidence labels. Primary,
duplicate, and adjudicated records remain separate.

## 6. Router, calibration, and cost

The learned routers are Logistic Regression and XGBoost with hyperparameters
stored in `configs/pilot-v1.yaml`. Primary features must exist after BM25 and a
bounded metadata-only lookup. Reranker results, fetched graph targets, and
post-execution overlap are diagnostic features only.

Logistic Regression uses its native probability. XGBoost uses Platt scaling.
Isotonic regression is a sensitivity analysis only when the calibration
partition has at least 100 question-path pairs and both classes.

The fold threshold is the smallest distinct calibrated probability whose
accepted decisions have empirical failure rate at most 0.10 and include at
least 10 questions. When no threshold qualifies, the fold forces full
abstention. Outer-test predictions are never searched for a replacement
threshold.

Eligible paths are selected by the lexicographic tuple:

`(neural calls, graph targets, context items, median runtime ms, path ID)`.

The no-abstention learned policy first uses the same calibrated threshold. If
no path meets it, the policy selects maximum probability and resolves ties with
the same cost tuple.

## 7. Go/No-Go rule

Progression requires all three qualitative gates and at least four of five
quantitative signals:

1. At least 20% of all 120 questions fail on `P0` and succeed on another path.
2. At least two downstream stages each rescue at least five unique questions
   under the frozen matched comparisons.
3. Oracle routing meets at least one frozen practical improvement in success,
   routable-only neural calls, or routable-only harmful expansion.
4. A no-abstention learned router beats the frozen heuristic under one frozen
   quality or cost condition, with the favorable direction in at least three
   folds.
5. Calibration-only thresholds yield coverage at least 20%, accepted risk at
   most 10%, and risk at least five percentage points below the same router
   without abstention.

Exact inequalities and comparison populations are stored in
`configs/pilot-v1.yaml`. Non-routable questions remain in all-question quality
and coverage results but are excluded from Oracle cost and harm comparisons.

## 8. Reproducibility and privacy

Every run records the code commit, all configuration hashes, corpus hash, model
state, seed, schema version, timestamp, input hashes, and output hashes. Public
artifacts contain only permitted identifiers and metadata. Source corpora,
database snapshots, credentials, machine-local paths, and private review
worksheets remain outside version control.

Before any Pilot path labels were created, the version-1 identifier schema was
corrected on 2026-07-25 to admit native regulatory identifiers containing
spaces and slashes while continuing to reject empty values, control characters,
and values longer than 128 characters. Identifiers remain verbatim stable
source keys; they are not rewritten or replaced with runtime database IDs.
