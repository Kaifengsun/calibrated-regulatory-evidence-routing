# Pilot-First Calibrated Evidence Routing Design

Date: 2026-07-23  
Status: Approved for specification review  
Repository: `calibrated-regulatory-evidence-routing`

## 1. Purpose

This repository will support a bounded research study on calibrated, query-adaptive evidence routing for regulatory retrieval. The study will test whether a lightweight router can select the least costly evidence path that still retrieves complete evidence, and abstain when no evaluated path is likely to be sufficient.

The repository is intentionally pilot-first. Full dataset construction and model development will proceed only if a new two-domain pilot demonstrates that routing decisions are useful and learnable.

## 2. Research Question

Given a BM25 first-stage retrieval result and a fixed set of downstream evidence paths, can a calibrated lightweight model select a path that:

1. retrieves complete attributable evidence;
2. minimizes irrelevant or harmful evidence expansion;
3. reduces computation relative to enabling every module; and
4. abstains when no available path is expected to retrieve sufficient evidence?

The study covers two regulatory domains:

- Chinese chemical-safety standards;
- English pharmaceutical regulatory and supply-chain documents.

Because domain and language change together, all cross-domain conclusions must be described as two-domain transfer results rather than language-independent domain generalization.

## 3. Scope

### 3.1 Included

- BM25 as the fixed first-stage retriever.
- One frozen neural reranker selected before pilot evaluation.
- Parent, heading, and text-based table-context augmentation.
- One-hop traversal of `CITES` and `DEPENDS_ON`.
- Fixed rules, BM25-only, all-modules, and oracle baselines.
- Logistic Regression and XGBoost route-success predictors.
- Probability calibration and evidence-sufficiency abstention.
- Document-grouped validation and two-direction cross-domain transfer.
- Reproducible experiment manifests, frozen query sets, and bootstrap uncertainty intervals.

### 3.2 Excluded

- Training a new Transformer retriever or reranker.
- Agent workflows.
- Multi-hop graph reasoning.
- Multimodal table-image or cell-level retrieval.
- Generated-answer evaluation and atomic claim verification.
- Large-scale comparisons across multiple language models.
- Copying copyrighted source corpora, database snapshots, or internal review files into this repository.

## 4. Repository Boundary

The repository may contain:

- original source code for the new study;
- experiment configuration and environment specifications;
- schemas, templates, and annotation guidelines;
- anonymized or redistribution-safe pilot records;
- hashes and local path placeholders for non-redistributable inputs;
- aggregate results and publication artifacts.

The repository must not contain:

- copyrighted regulatory full text without redistribution permission;
- Neo4j database snapshots from the prior projects;
- credentials, API keys, personal identifiers, or absolute developer-machine paths;
- private reviewer worksheets containing restricted source passages.

Non-redistributable inputs will be referenced through ignored local configuration files. A committed example configuration will document required keys without real paths or secrets.

## 5. Candidate Evidence Paths

The pilot will begin with six frozen paths:

| Path | Definition |
|---|---|
| P0 | BM25 only |
| P1 | BM25 followed by the frozen neural reranker |
| P2 | BM25 followed by parent, heading, or table-text context augmentation |
| P3 | BM25 followed by one-hop `CITES` or `DEPENDS_ON` expansion |
| P4 | BM25, neural reranking, then context augmentation |
| P5 | BM25 with all eligible downstream modules enabled |

The pilot may remove a path before full-dataset construction when that path never provides independent utility. New paths may not be added after pilot evaluation unless the protocol is versioned and the pilot is rerun.

Abstention is not a seventh retrieval path. The router abstains when every available path has calibrated success probability below a frozen threshold.

## 6. Pilot Dataset

### 6.1 Size

The initial pilot will contain 120 newly written questions:

- 60 chemical-safety questions;
- 60 pharmaceutical-regulatory questions.

Each domain will be sampled approximately evenly across:

- direct-clause needs;
- parent or heading context needs;
- table-related needs;
- citation or dependency needs;
- evidence-insufficient needs.

These sampling categories are construction controls, not route labels and not direct model targets.

### 6.2 Query Construction

Questions must be new and must not reproduce questions from either prior manuscript's observed evaluation set. Question writers may inspect source evidence needed to express a realistic information need but must not inspect candidate rankings from the new pipelines before freezing the query.

The pilot must include counter-cue cases so that routing cannot be solved by trivial keywords alone:

- a query with relation language whose direct clause is sufficient;
- a query without explicit relation language that requires a cited clause;
- a query mentioning a table whose answer is in prose;
- a high-ranked but scope-incomplete BM25 result;
- a reasonable query for which the available corpus lacks complete evidence.

### 6.3 Splitting

All train, calibration, validation, and test splits must be grouped by source document or standard. Questions derived from the same clause, table, relation, or document family must not cross split boundaries.

The pilot is primarily a feasibility study and will use grouped cross-validation. A final untouched test set will be created only after the go decision and full-dataset expansion.

## 7. Evidence and Path Labels

The fundamental observation is a question-path pair, not a single best route assigned to a question.

For question `q` and path `p`:

`success(q, p) = 1` only when path `p` retrieves all evidence required by the frozen evidence specification within the evaluated cutoff and does not introduce a predefined harmful expansion.

Otherwise:

`success(q, p) = 0`.

Annotations must distinguish:

- corpus insufficiency: the frozen corpus does not contain complete evidence;
- retrieval failure: complete evidence exists but the path does not recover it;
- harmful expansion: added evidence is unsupported, misleading, or materially distracts from the required evidence;
- harmless extra context: additional attributable evidence that does not change or obscure the answer.

At least 25% of records must receive independent duplicate annotation. Disagreements must be adjudicated while preserving both original labels and the adjudication record.

## 8. Router Design

### 8.1 Prediction Target

For each candidate path, a lightweight model will estimate:

`P(success(q, p) = 1 | query features, first-stage features, path features)`.

The selected path is the lowest-cost path whose calibrated success probability meets the frozen sufficiency threshold. If no path meets the threshold, the system abstains.

### 8.2 Initial Models

- Logistic Regression.
- XGBoost.

No neural router will be introduced during the pilot.

### 8.3 Initial Features

Features should emphasize domain-portable retrieval behavior:

- BM25 top-score magnitude;
- first-to-second and first-to-k score gaps;
- top-k score entropy or dispersion;
- query and candidate length;
- explicit standard, section, table, identifier, and relation cues;
- candidate overlap across retrieval methods;
- graph degree, eligible edge count, relation type, and stored confidence;
- agreement between lexical retrieval and the frozen reranker.

Raw query embeddings are optional and must be evaluated separately. If used, they must come from one frozen multilingual model and must not become the only basis for the cross-domain claim.

## 9. Calibration and Abstention

Calibration will be fitted only on the calibration partition within each grouped split. Candidate methods are:

- Platt scaling for Logistic Regression where additional calibration is required;
- isotonic regression only when calibration sample size is sufficient;
- the corresponding calibrated-probability procedure selected for XGBoost before final testing.

The abstention threshold must be selected on calibration data under a frozen evidence-risk constraint. Test data must not be used to choose the threshold.

The paper will describe abstention as evidence-sufficiency abstention. It will not claim guaranteed answer correctness because generated answers are outside the study scope.

## 10. Cost and Selection Objective

Each path will have a deterministic cost profile derived from:

- measured median runtime;
- number of downstream model calls;
- number of graph expansions;
- number of evidence items added.

Primary route selection will minimize path cost subject to a calibrated minimum probability of complete evidence. Weighted utility scores may be reported only as sensitivity analyses because arbitrary weights can obscure the quality-risk-cost trade-off.

## 11. Baselines

The pilot and full study will include:

- BM25-only;
- all eligible modules enabled;
- fixed heuristic routing;
- Logistic Regression routing;
- XGBoost routing;
- oracle lowest-cost successful path.

The oracle is an upper-bound diagnostic and must never be described as a deployable method.

## 12. Metrics

Primary metrics:

- complete evidence retrieval at the frozen cutoff;
- harmful expansion rate;
- route cost at a fixed evidence-completeness constraint;
- selective risk and coverage under abstention.

Secondary metrics:

- Recall@k and MRR for source evidence;
- Brier score;
- Expected Calibration Error with frozen binning;
- route-selection accuracy as a descriptive metric;
- latency and downstream-call count;
- paired bootstrap confidence intervals.

Results must be reported per domain, pooled across domains, and for chemical-to-pharmaceutical and pharmaceutical-to-chemical transfer.

## 13. Pilot Go/No-Go Decision

The project proceeds to full-dataset construction only when the pilot demonstrates all of the following qualitative conditions and at least four of the five quantitative signals:

Qualitative conditions:

- no single fixed route trivially dominates both evidence quality and cost;
- annotations can reliably distinguish complete evidence, retrieval failure, and corpus insufficiency;
- route differences survive inspection for construction artifacts and trivial lexical cues.

Quantitative signals:

1. At least 20% of pilot questions require a path beyond BM25 for complete evidence.
2. At least two downstream module types provide independent benefit on multiple questions.
3. Oracle routing improves completeness over BM25-only or reduces cost/harm relative to all-modules.
4. At least one lightweight learned router outperforms the best fixed rule under grouped validation on the primary constrained-cost evaluation.
5. Calibration produces a non-degenerate risk-coverage trade-off with meaningful abstention behavior.

If these conditions fail, the routing claim will not be expanded. The project will either publish a narrower negative/diagnostic result if defensible or stop and move to the separately scoped table-retrieval Plan B.

## 14. Data Flow

1. Load local domain configuration.
2. Validate corpus identity and frozen hashes.
3. Load a frozen query record and its evidence specification.
4. Run BM25 once and cache the first-stage result.
5. Execute each frozen downstream path against the same cached first-stage result.
6. Store attributable candidates, runtime, module calls, graph paths, and errors.
7. Produce blinded annotation records.
8. Import reviewed labels without overwriting original annotations.
9. Build grouped modeling splits.
10. Train and calibrate lightweight route-success predictors.
11. Evaluate fixed, learned, and oracle policies.
12. Export aggregate tables, confidence intervals, and reproducibility manifests.

## 15. Error Handling and Reproducibility

- A failed path execution must be recorded as an error, not silently converted into a retrieval miss.
- Every experiment run must record configuration hash, code commit, corpus hash, model identifier, seed, and timestamp.
- Cached results must include schema version and input hashes.
- Frozen evaluation files must be immutable; corrected versions require a new version identifier and a change log.
- Secrets and local paths must be loaded from ignored files or environment variables.
- Random operations must use declared seeds.

## 16. Testing Strategy

The implementation plan must include tests for:

- schema validation for queries, evidence specifications, path outputs, and annotations;
- deterministic BM25 and fixed-path execution on fixtures;
- document-group split leakage detection;
- cost-accounting correctness;
- oracle policy correctness;
- calibration fitting without test-set access;
- abstention threshold application;
- experiment manifest completeness;
- prevention of restricted or absolute-path data from entering tracked files.

## 17. Planned Repository Structure

```text
.
├── README.md
├── LICENSE
├── .gitignore
├── configs/
│   └── local.example.yaml
├── data/
│   ├── README.md
│   ├── schemas/
│   └── templates/
├── docs/
│   ├── annotation/
│   ├── protocol/
│   └── superpowers/specs/
├── plan/
├── src/
│   └── evidence_routing/
├── tests/
└── pyproject.toml
```

This structure is a target for the implementation plan, not permission to add unused modules during initial scaffolding.

## 18. Completion Boundary for the First Implementation Plan

The first implementation plan will stop after:

- repository scaffolding;
- reproducibility and privacy safeguards;
- Pilot protocol and schemas;
- local corpus adapters with no committed source data;
- fixed path execution interfaces;
- Pilot feasibility analysis.

Full-dataset expansion, final model comparison, manuscript generation, and Plan B implementation require separate go decisions and plans.
