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
| P0 | BM25 top 10 only |
| P1 | BM25 top 50, followed by the frozen neural reranker, returning its top 10 |
| P2 | BM25 top 10, with deterministic context augmentation applied to the first five results |
| P3 | BM25 top 10, with deterministic graph expansion applied to the first five results |
| P4 | BM25 top 50, neural reranking to top 10, then deterministic context augmentation of the first five results |
| P5 | BM25 top 50, neural reranking to top 10, deterministic context augmentation of the first five results, then deterministic graph expansion from those five results |

The pilot may remove a path before full-dataset construction when that path never provides independent utility. New paths may not be added after pilot evaluation unless the protocol is versioned and the pilot is rerun.

Abstention is not a seventh retrieval path. The router abstains when every available path has calibrated success probability below a frozen threshold.

### 5.1 Frozen Module Parameters

The Pilot protocol must record the exact reranker model repository, revision, tokenizer revision, inference precision, maximum input length, prompt format, batch size, and tie-breaking rule before any Pilot path labels are inspected. The initial candidate is `Qwen/Qwen3-Reranker-0.6B`; a different model may be chosen only before the protocol freeze.

Context augmentation is metadata-preserving and does not perform a new semantic search. For each of the first five ranked Sections, it may attach:

1. the Section's own heading path;
2. the immediate parent Section title and source text, when present;
3. directly linked table title and table-text description when the query contains a table cue or the retrieved Section has a direct table attachment.

Context items are ordered within each seed by context type in the order heading path, immediate parent, table, then by stable source identifier. A maximum of three context items may be attached to each seed. Context items retain their source identifiers and never replace the seed or occupy a ranked-result position. They are sidecar evidence attached to one of the first five ranked seeds.

Graph expansion starts from the first five ranked Section seeds. It follows only one outgoing `CITES` or `DEPENDS_ON` edge with stored confidence at least `0.85`. Eligible targets are ordered by source-seed rank, descending edge confidence, relation type, and stable target identifier. At most five unique targets are inserted after the five seeds and before the remaining direct results. A target already present in the direct list is not duplicated. Final evaluation uses the first ten evidence units.

P5 uses the exact order stated in the table: rerank, select five seeds, attach context to those seeds, expand graph relations from the same five Section seeds, then assemble the final evidence package. The final ranked list preserves the five seeds, inserts up to five graph targets, and then fills any unused positions from the reranked direct remainder. The evaluated ranked cutoff is ten. Context items remain sidecar evidence attached to the five seeds and are evaluated separately from ranked positions.

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

The pilot is primarily a feasibility study and will use deterministic five-fold grouped cross-validation. Document groups are assigned to folds by a stable hash under a frozen seed, with stratification by domain and construction category when feasible.

For pooled and within-domain evaluation, outer fold `i` is the test fold, fold `(i + 1) mod 5` is the calibration fold, and the remaining three folds are training folds. Hyperparameters are frozen before the five-fold run; the test fold is never used for model selection, probability calibration, or abstention-threshold selection.

Cross-domain transfer is evaluated separately in both directions. The base model is fitted on all source-domain records. Its probability calibrator and abstention threshold are fitted from source-domain grouped out-of-fold predictions only. The complete target domain is then evaluated without target-domain fitting, calibration, threshold selection, or feature normalization. Cross-domain transfer is a descriptive Pilot diagnostic because each domain initially contains only 60 questions.

A final untouched test set will be created only after the go decision and full-dataset expansion.

## 7. Evidence and Path Labels

The fundamental observation is a question-path pair, not a single best route assigned to a question.

For question `q` and path `p`:

`success(q, p) = 1` only when path `p` retrieves all evidence required by the frozen evidence specification through either the first ten ranked evidence units or the context sidecars attached to the first five seeds, and does not introduce a harmful expansion in that evaluated package.

Otherwise:

`success(q, p) = 0`.

Annotations must distinguish:

- corpus insufficiency: the frozen corpus does not contain complete evidence;
- retrieval failure: complete evidence exists but the path does not recover it;
- harmful expansion: added evidence is unsupported, misleading, or materially distracts from the required evidence;
- harmless extra context: additional attributable evidence that does not change or obscure the answer.

`corpus insufficiency` may be assigned only after an annotator performs a documented manual check of the frozen corpus and confirms that the complete evidence specification cannot be satisfied. Failure of all six candidate paths is not evidence of corpus insufficiency and must not be used to infer that label. When the manual check finds that evidence exists outside all six path outputs, the record is a retrieval failure.

Each candidate evidence unit is assigned one of five labels:

- `REQUIRED`: necessary for the complete evidence specification;
- `SUFFICIENT`: independently supports the information need without another required unit;
- `CONTEXT`: attributable and useful but not required;
- `IRRELEVANT`: does not support the information need but is not misleading;
- `HARMFUL`: contradicts the applicable evidence, changes its scope incorrectly, refers to the wrong regulated object or version, or is sufficiently misleading that including it could change the interpretation.

A path has complete evidence when every `REQUIRED` evidence identifier is present either in the first ten ranked units or in an eligible context sidecar attached to a top-five seed, or when at least one `SUFFICIENT` item satisfies a single-item evidence specification. `IRRELEVANT` items do not by themselves cause failure. Any `HARMFUL` ranked item within the first ten or any `HARMFUL` attached context sidecar causes the path's success label to be zero. Context attachments inherit separate identifiers and labels; they do not receive relevance by association with their seed.

At least 25% of records must receive independent duplicate annotation. Disagreements must be adjudicated while preserving both original labels and the adjudication record.

The annotation guideline must provide positive and negative examples for `HARMFUL` in the following decision order:

1. wrong regulatory document or standard version;
2. wrong regulated object, product, substance, organization, or jurisdiction;
3. incorrect scope, responsible party, condition, threshold, or exception;
4. direct conflict with the applicable evidence;
5. otherwise misleading evidence that could materially alter the regulatory interpretation.

Ordinary background noise, redundant evidence, and weakly related material are `IRRELEVANT`, not `HARMFUL`, unless one of the five conditions above applies.

The combined path-success definition is intentionally risk-averse for regulatory retrieval: complete evidence plus one `HARMFUL` item is still a failed path. Evaluation must therefore report three outcomes separately:

- evidence completeness without applying the harm rule;
- harmful expansion rate;
- combined path success after applying both completeness and harm requirements.

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

Primary route-time features must be available after the single BM25 run and a bounded metadata-only lookup. Executing the reranker, fetching graph targets, or assembling a downstream path before route selection is prohibited. Primary features should emphasize domain-portable retrieval behavior:

- BM25 top-score magnitude;
- first-to-second and first-to-k score gaps;
- top-k score entropy or dispersion;
- query and candidate length;
- explicit standard, section, table, identifier, and relation cues;
- graph degree, count of eligible outgoing edges, available relation types, and maximum stored edge confidence obtained without fetching target text;
- path identity and the path's static cost fields.

Raw query embeddings are optional and must be evaluated separately. If used, they must come from one frozen multilingual model and must not become the only basis for the cross-domain claim.

Reranker agreement, candidate overlap across executed methods, retrieved graph-target properties, and other post-execution values may be analyzed as oracle or diagnostic features only. They must not be inputs to the primary deployable router and their computation must not be included in claims of route-time cost savings.

## 9. Calibration and Abstention

Calibration will be fitted only on the calibration partition within each grouped split. Candidate methods are:

- unmodified Logistic Regression probability as the default Logistic Regression output;
- Platt scaling applied to XGBoost scores;
- isotonic regression only as a sensitivity analysis when the calibration partition contains at least 100 question-path pairs and both outcome classes.

For each evaluation fold, the abstention threshold is the smallest candidate threshold on the calibration data for which the empirical failure rate among accepted route decisions is at most `0.10` and at least ten question decisions are accepted. Candidate thresholds are the distinct calibrated probabilities observed on the calibration partition. If no threshold satisfies both conditions, the policy records `force_abstain = true` and abstains for every item in that evaluation fold regardless of predicted probability. Degenerate coverage is reported rather than repaired with test data.

The paper will describe abstention as evidence-sufficiency abstention. It will not claim guaranteed answer correctness because generated answers are outside the study scope.

Every learned router also has a frozen no-abstention variant for fair comparison with the non-abstaining heuristic. The no-abstention variant selects the lexicographically lowest-cost path among paths meeting the calibrated threshold. When no path meets the threshold, it selects the path with the highest calibrated success probability; ties are resolved by the lexicographic cost tuple in Section 10. This fallback is used only to define a route for every question and does not alter the calibrated abstention policy.

## 10. Cost and Selection Objective

Each path will have a deterministic cost profile derived from:

- number of neural-model calls;
- number of graph targets inserted;
- number of context items attached;
- measured median runtime.

Primary route selection uses the following lexicographic cost tuple:

`(neural_model_calls, graph_targets_inserted, context_items_attached, median_runtime_ms, path_id)`.

Among paths meeting the calibrated success threshold, the router selects the lexicographically smallest tuple. Runtime is measured under the frozen Pilot environment and rounded to the nearest millisecond. `path_id` provides deterministic final tie-breaking. This ordering treats neural inference as the most expensive optional operation and avoids an arbitrary weighted sum.

Weighted utility scores may be reported only as sensitivity analyses because arbitrary weights can obscure the quality-risk-cost trade-off.

## 11. Baselines

The pilot and full study will include:

- BM25-only;
- all eligible modules enabled;
- fixed heuristic routing;
- Logistic Regression routing;
- XGBoost routing;
- oracle lowest-cost successful path.

The oracle is an upper-bound diagnostic and must never be described as a deployable method.

### 11.1 Frozen Heuristic Router

The fixed heuristic router is frozen before Pilot path labels are inspected. Cue dictionaries are stored in a versioned protocol file. Let the normalized BM25 ambiguity gap be `(score_1 - score_2) / max(abs(score_1), epsilon)`, with `epsilon = 1e-9`.

The heuristic selects:

1. `P5` when both a frozen table/context cue and a frozen citation/dependency cue occur;
2. `P3` when only a frozen citation/dependency cue occurs;
3. `P2` when only a frozen table/context cue occurs;
4. `P1` when neither cue class occurs and the normalized ambiguity gap is below `0.15`;
5. `P0` otherwise.

The heuristic does not abstain. The threshold `0.15`, cue dictionaries, cue precedence, and Unicode normalization procedure may be changed only before protocol freeze. No alternative heuristic may replace it after Pilot labels are observed. Post hoc heuristic variants may appear only as clearly labelled sensitivity analyses and cannot satisfy the go/no-go comparison.

## 12. Metrics

Primary metrics:

- complete evidence retrieval over the first ten ranked units plus eligible context sidecars;
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
2. At least two of the three downstream module types each provide independently attributable benefit on at least five unique Pilot questions. An independent benefit requires a matched comparison in which the path without the module fails and the otherwise corresponding path with the module succeeds: reranker uses `P1` versus `P0`; context uses either `P2` versus `P0` or `P4` versus `P1`; graph uses either `P3` versus `P0` or `P5` versus `P4`.
3. Oracle routing satisfies at least one of the following minimum practical differences: (a) combined path success is at least 5 percentage points higher than `P0`; (b) combined path success is no more than 2 percentage points below `P5` while mean neural-model calls are at least 20% lower than `P5`; or (c) harmful expansion rate is at least 5 percentage points lower than `P5` while evidence completeness is no more than 2 percentage points lower.
4. At least one lightweight learned router, operated in the no-abstention mode defined in Section 9, satisfies one of the following against the frozen heuristic router on all Pilot questions using pooled out-of-fold predictions: (a) combined path success is at least 5 percentage points higher and the fold-level difference has the same positive direction in at least three of five outer folds; or (b) combined path success is no more than 2 percentage points lower, mean neural-model calls are at least 20% lower, and the neural-call difference has the same favorable direction in at least three of five outer folds. Abstentions do not enter Signal 4.
5. Calibration yields at least one non-forced-abstention operating point with coverage of at least 20%, empirical failure rate among accepted decisions no greater than 10%, and accepted-decision failure rate at least 5 percentage points lower than the all-question failure rate of the same learned router operated in the no-abstention mode defined in Section 9. Coverage, accepted-decision risk, abstention rate, and the no-abstention all-question risk must be reported separately.

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
|-- README.md
|-- LICENSE
|-- .gitignore
|-- configs/
|   `-- local.example.yaml
|-- data/
|   |-- README.md
|   |-- schemas/
|   `-- templates/
|-- docs/
|   |-- annotation/
|   |-- protocol/
|   `-- superpowers/specs/
|-- plan/
|-- src/
|   `-- evidence_routing/
|-- tests/
`-- pyproject.toml
```

This structure is a target for the implementation plan, not permission to add unused modules during initial scaffolding.

## 18. Completion Boundary for the First End-to-End Pilot Plan

The first implementation plan will stop after:

- repository scaffolding;
- reproducibility and privacy safeguards;
- a versioned and frozen Pilot protocol, including the exact reranker identity and parameters;
- query, evidence-specification, path-output, annotation, adjudication, split, and manifest schemas;
- construction and freeze of all 120 new Pilot questions and their evidence specifications;
- local corpus adapters with no committed source data;
- implementation and successful execution of all retained fixed paths on every frozen Pilot question;
- blinded annotation export and reviewed-label import;
- completion of the required primary annotations, at least 25% independent duplicate annotation, agreement analysis, adjudication, and preservation of original labels;
- Logistic Regression, XGBoost, fixed-rule, all-modules, BM25-only, and oracle policies;
- grouped calibration and abstention-threshold fitting;
- completed within-domain, pooled, and two-direction transfer Pilot runs;
- automatic computation of every Pilot go/no-go signal;
- a versioned Pilot feasibility report that records the decision and evidence for each criterion in Section 13.

Full-dataset expansion, final model comparison, manuscript generation, and Plan B implementation require separate go decisions and plans.
