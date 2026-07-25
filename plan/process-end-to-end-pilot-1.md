---
goal: Execute the frozen 120-question calibrated regulatory evidence-routing Pilot and produce a reproducible Go/No-Go decision
version: 1.0
date_created: 2026-07-23
last_updated: 2026-07-23
owner: Kaifeng Sun
status: 'In progress'
tags: [process, research, pilot, retrieval, calibration, reproducibility]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

This plan implements the approved Pilot-first design in `docs/superpowers/specs/2026-07-23-pilot-first-evidence-routing-design.md`. Completion requires construction and freeze of 120 new questions, execution and annotation of all six frozen evidence paths, lightweight route modeling, calibration, abstention evaluation, cross-domain transfer analysis, and an automatically computed Go/No-Go report.

## 1. Requirements & Constraints

- **REQ-001**: Use BM25 as the only first-stage retriever for every path.
- **REQ-002**: Implement exactly six Pilot paths, `P0` through `P5`, using the execution order and cutoffs in the approved design.
- **REQ-003**: Construct exactly 120 new Pilot questions: 60 chemical-safety and 60 pharmaceutical-regulatory questions.
- **REQ-004**: Evaluate ranked evidence at cutoff 10 and context sidecars attached only to the first five seeds.
- **REQ-005**: Preserve the five-label evidence scheme: `REQUIRED`, `SUFFICIENT`, `CONTEXT`, `IRRELEVANT`, and `HARMFUL`.
- **REQ-006**: Independently duplicate-annotate exactly 30 complete questions, including all path outputs and associated evidence labels.
- **REQ-007**: Implement BM25-only, all-modules, frozen heuristic, Logistic Regression, XGBoost, and oracle policies.
- **REQ-008**: Fit calibrators and abstention thresholds without test-fold access.
- **REQ-009**: Compute all five quantitative and all qualitative Go/No-Go signals without manual arithmetic.
- **REQ-010**: Produce within-domain, pooled, chemical-to-pharmaceutical, and pharmaceutical-to-chemical results.
- **CON-001**: Do not commit copyrighted regulatory text, Neo4j snapshots, restricted reviewer worksheets, credentials, API keys, or developer-machine absolute paths.
- **CON-002**: Do not add a neural router, Agent workflow, multi-hop graph reasoning, multimodal table retrieval, or generated-answer evaluation.
- **CON-003**: Do not reuse observed evaluation questions from either prior manuscript.
- **CON-004**: Group all modeling splits by source document or standard.
- **CON-005**: Treat Chinese chemical-safety to English pharmaceutical-regulatory transfer as joint domain-and-language transfer.
- **CON-006**: Freeze the reranker identity, revision, inference parameters, cue dictionaries, schemas, seeds, and path parameters before inspecting Pilot path labels.
- **SEC-001**: Load local paths and secrets only from ignored files or environment variables.
- **SEC-002**: Run an automated tracked-file privacy scan before every release commit.
- **DAT-001**: Infer `corpus_insufficiency` only after a documented manual frozen-corpus check; never infer it from six path failures.
- **DAT-002**: Preserve primary labels, duplicate labels, adjudicated labels, annotator identity codes, and timestamps as separate immutable fields.
- **GUD-001**: Prefer deterministic, inspectable implementations over reusable framework abstractions.
- **GUD-002**: Record negative findings and failed paths without post hoc path changes.
- **PAT-001**: Every experiment artifact must record code commit, configuration hash, corpus hash, model revision, seed, schema version, and timestamp.

## 2. Implementation Steps

### Implementation Phase 1: Repository and Source-System Inventory

- GOAL-001: Create a safe, reproducible project shell and document how the two existing source systems can be accessed without copying restricted data.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `README.md` with the research question, Pilot scope, repository boundary, current phase, and links to the approved design and this plan. | ✅ | 2026-07-23 |
| TASK-002 | Create `.gitignore` covering `.env`, `configs/local.yaml`, databases, indexes, model caches, raw corpora, private annotations, generated logs, and Python build artifacts. | ✅ | 2026-07-23 |
| TASK-003 | Create `pyproject.toml` for Python 3.11 or later with runtime dependencies `pydantic`, `pyyaml`, `numpy`, `pandas`, `scikit-learn`, `xgboost`, `scipy`, `typer`, and development dependencies `pytest`, `pytest-cov`, and `ruff`. | ✅ | 2026-07-23 |
| TASK-004 | Create `src/evidence_routing/__init__.py` and `src/evidence_routing/cli.py`; expose a Typer application with commands `validate-config`, `validate-data`, `run-paths`, `export-annotation`, `import-annotation`, `fit-router`, `evaluate`, and `go-no-go`. | ✅ | 2026-07-23 |
| TASK-005 | Create `configs/local.example.yaml` with keys for both source-system roots, Neo4j connection placeholders, local export paths, model cache, artifact root, and secrets supplied through environment-variable names. | ✅ | 2026-07-23 |
| TASK-006 | Inspect the read-only project configured by `CER_CHEMICAL_PROJECT_ROOT` and record available retrieval entry points, node identifiers, relation fields, table fields, corpus hashes, and required services in `docs/protocol/source-system-inventory.md`. | ✅ | 2026-07-23 |
| TASK-007 | Inspect the read-only project configured by `CER_PHARMA_PROJECT_ROOT` and record available retrieval entry points, source identifiers, hierarchy fields, graph-chain fields, corpus hashes, and required services in `docs/protocol/source-system-inventory.md`. | ✅ | 2026-07-23 |
| TASK-008 | Implement `src/evidence_routing/privacy.py::scan_tracked_files` to fail on absolute developer paths, secret-like assignments, prohibited filename patterns, and files over the frozen size limit; add `tests/test_privacy.py`. | ✅ | 2026-07-23 |

Completion criteria:

- `pytest` passes for the initial package and privacy scanner.
- `python -m evidence_routing.cli validate-config --config configs/local.example.yaml` reports only expected missing local values.
- `git ls-files` contains no restricted data or machine-specific paths.
- `docs/protocol/source-system-inventory.md` identifies a feasible read-only adapter route for each domain or records a blocking dependency explicitly.

### Implementation Phase 2: Frozen Pilot Protocol and Schemas

- GOAL-002: Convert every design rule that affects labels, paths, splitting, calibration, or Go/No-Go into a versioned machine-readable protocol.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Create `configs/pilot-v1.yaml` with seed `20260723`, domains, exact question counts, path IDs, BM25 depths, output cutoff 10, top-five seed policy, graph confidence `0.85`, graph target cap 5, context sidecar cap 3 per seed, duplicate-question count 30, five-fold assignment, calibration rule, and all Section 13 thresholds. | ✅ | 2026-07-24 |
| TASK-010 | Create `configs/cues-v1.yaml` containing versioned Chinese and English table/context and citation/dependency cue dictionaries plus Unicode normalization rules. | ✅ | 2026-07-24 |
| TASK-011 | Create `configs/reranker-v1.yaml` with the selected reranker repository, immutable revision, tokenizer revision, prompt format, precision, maximum input length, batch size, score interpretation, and stable tie-breaking rule. | ✅ | 2026-07-24 |
| TASK-012 | Create Pydantic models in `src/evidence_routing/schemas.py` for `QueryRecord`, `EvidenceSpecification`, `RankedEvidenceUnit`, `ContextSidecar`, `PathRun`, `EvidenceAnnotation`, `QuestionAnnotationBundle`, `AdjudicationRecord`, `SplitAssignment`, and `ExperimentManifest`. | ✅ | 2026-07-24 |
| TASK-013 | Create JSON Schemas under `data/schemas/` from the Pydantic models and create redistribution-safe examples under `data/templates/`. | ✅ | 2026-07-24 |
| TASK-014 | Implement `src/evidence_routing/validation.py::validate_dataset`, `validate_path_run`, `validate_annotation_bundle`, and `validate_manifest`; reject unknown schema versions and identifier collisions. | ✅ | 2026-07-24 |
| TASK-015 | Create `docs/protocol/pilot-v1.md` explaining the frozen execution protocol in human-readable form and recording the SHA-256 hashes of `pilot-v1.yaml`, `cues-v1.yaml`, and `reranker-v1.yaml`. | ✅ | 2026-07-24 |
| TASK-016 | Add `tests/test_schemas.py`, `tests/test_validation.py`, and fixtures covering valid records, invalid identifiers, missing provenance, duplicate evidence units, illegal path IDs, and prohibited corpus-insufficiency inference. | ✅ | 2026-07-24 |

Dependencies: TASK-009 through TASK-016 depend on TASK-006 and TASK-007 for field mapping but not on live corpus execution.

Completion criteria:

- Every template validates through `validate-data`.
- Every invalid fixture fails with a stable error code.
- Protocol hashes can be reproduced from a clean checkout.
- No Pilot path result or annotation has been inspected before the freeze commit is created.

### Implementation Phase 3: Domain Adapters and BM25 Contract

- GOAL-003: Produce one normalized, provenance-preserving retrieval contract for both domains.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | Define `src/evidence_routing/adapters/base.py::RegulatoryCorpusAdapter` with methods `corpus_manifest`, `bm25_search`, `get_section`, `get_context_sidecars`, `get_graph_metadata`, `expand_graph`, and `manual_corpus_search`. | ✅ | 2026-07-24 |
| TASK-018 | Implement `src/evidence_routing/adapters/chemical.py::ChemicalSafetyAdapter` using the read-only entry points recorded in the source-system inventory. | ✅ | 2026-07-24 |
| TASK-019 | Implement `src/evidence_routing/adapters/pharma.py::PharmaceuticalRegulatoryAdapter` using the read-only entry points recorded in the source-system inventory. | ✅ | 2026-07-24 |
| TASK-020 | Implement `src/evidence_routing/retrieval.py::run_bm25_once` to return a deterministic top-50 normalized candidate list with stable source identifiers and unmodified source scores. | ✅ | 2026-07-24 |
| TASK-021 | Implement `src/evidence_routing/cache.py::ResultCache` keyed by domain, corpus hash, query hash, protocol hash, path ID, and code commit. | ✅ | 2026-07-24 |
| TASK-022 | Add adapter contract tests in `tests/test_adapters.py` using redistribution-safe fixtures; verify stable ordering, provenance completeness, parent/table resolution, graph metadata lookup, and no source mutation. | ✅ | 2026-07-24 |

Dependencies: TASK-017 precedes TASK-018 through TASK-022. Live integration tests require the local services recorded by TASK-006 and TASK-007.

Completion criteria:

- The same `QueryRecord` interface executes against both adapters.
- Repeated BM25 fixture runs return byte-identical serialized output.
- Every returned unit includes domain, document ID, source ID, source type, and corpus hash.

### Implementation Phase 4: Six Frozen Evidence Paths

- GOAL-004: Implement and verify `P0` through `P5` exactly as specified without post-label tuning.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-023 | Implement `src/evidence_routing/paths.py::run_p0` as BM25 top 10. | ✅ | 2026-07-25 |
| TASK-024 | Implement `src/evidence_routing/reranking.py::FrozenReranker` and `paths.py::run_p1` as BM25 top 50 followed by frozen reranking to top 10. | ✅ | 2026-07-25 |
| TASK-025 | Implement `src/evidence_routing/context.py::attach_context` and `paths.py::run_p2`; preserve BM25 ranked units and attach ordered heading, immediate-parent, and eligible table-text sidecars to the first five seeds. | ✅ | 2026-07-25 |
| TASK-026 | Implement `src/evidence_routing/graph.py::expand_one_hop` and `paths.py::run_p3`; preserve five seeds, insert up to five deduplicated eligible graph targets, then fill from the BM25 remainder. | ✅ | 2026-07-25 |
| TASK-027 | Implement `paths.py::run_p4` as frozen reranking followed by context sidecars on the first five reranked seeds. | ✅ | 2026-07-25 |
| TASK-028 | Implement `paths.py::run_p5` as frozen reranking, context attachment, and graph expansion from the same five reranked Section seeds. | ✅ | 2026-07-25 |
| TASK-029 | Implement `src/evidence_routing/runner.py::run_all_paths` to run BM25 once, reuse the cached first stage, execute all six paths, isolate path errors, and write one `ExperimentManifest` per question. |  |  |
| TASK-030 | Add `tests/test_paths.py` covering ordering, top-five seed preservation, cutoff 10, context sidecar placement, graph confidence filtering, deduplication, stable ties, and P5 execution order. | ✅ | 2026-07-25 |

Completion criteria:

- Golden fixture outputs for all six paths are byte-identical across repeated runs.
- A failure in one downstream path is recorded as `execution_error` and does not alter another path's output.
- No path reads annotation labels.

### Implementation Phase 5: Pilot Question Construction and Annotation

- GOAL-005: Build, freeze, execute, and review the complete 120-question Pilot without question or label leakage.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-031 | Create `docs/annotation/question-construction-v1.md` with category quotas, counter-cue requirements, prohibited reuse rules, and a source-to-query audit checklist. | ✅ | 2026-07-25 |
| TASK-032 | Create `docs/annotation/evidence-labeling-v1.md` with the five evidence labels, corpus-insufficiency manual-check procedure, HARMFUL decision order, and positive and negative examples in both domains. | ✅ | 2026-07-25 |
| TASK-033 | Create exactly 60 chemical and 60 pharmaceutical `QueryRecord` plus `EvidenceSpecification` records in the local ignored authoring area; export only redistribution-safe identifiers and metadata to the tracked frozen dataset when permitted. |  |  |
| TASK-034 | Implement `src/evidence_routing/freeze.py::freeze_queries` to verify counts, quotas, uniqueness, source grouping, prior-benchmark non-overlap, and protocol hashes before writing the immutable Pilot version. |  |  |
| TASK-035 | Execute `run_all_paths` for every frozen question and verify 720 successful path manifests or explicit path-level execution errors. |  |  |
| TASK-036 | Implement `src/evidence_routing/annotation.py::export_blinded_workbook` and export randomized, method-blinded evidence units while preserving a private immutable mapping file outside version control. |  |  |
| TASK-037 | Implement `annotation.py::select_duplicate_questions` using the frozen seed to select exactly 30 stratified complete questions for the second annotator. |  |  |
| TASK-038 | Complete primary annotation for all 120 questions and independent duplicate annotation for all outputs of the selected 30 questions. |  |  |
| TASK-039 | Implement `annotation.py::import_reviewed_workbook`, `compute_agreement`, and `build_adjudication_queue`; preserve original labels and reject modified question/path identities. |  |  |
| TASK-040 | Complete adjudication, documented manual corpus checks, and final label freeze; write `artifacts/pilot-v1/annotation-manifest.json` without restricted source text. |  |  |

Human dependency:

- Kaifeng Sun supplies or confirms realistic information needs and completes the primary annotation.
- A second qualified reviewer independently annotates the frozen 30-question subset.
- Disagreements are adjudicated without replacing original labels.

Completion criteria:

- Exactly 120 questions and 720 question-path records are frozen.
- Exactly 30 complete questions have independent duplicate annotations.
- Every `corpus_insufficiency` label includes a manual-check record.
- Agreement statistics and adjudication counts reproduce from frozen labels.

### Implementation Phase 6: Features, Policies, Calibration, and Abstention

- GOAL-006: Train only the approved lightweight routers and produce leak-free route decisions.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-041 | Implement `src/evidence_routing/features.py::build_route_time_features` using only query, BM25, bounded graph metadata, path identity, and static cost fields available before downstream execution. |  |  |
| TASK-042 | Implement `features.py::build_diagnostic_features` separately; mark reranker agreement, executed-method overlap, and retrieved-target properties as non-deployable diagnostics. |  |  |
| TASK-043 | Implement `src/evidence_routing/splits.py::assign_grouped_folds` using stable document-group hashing and the rotation rule from the approved design; add explicit leakage assertions. |  |  |
| TASK-044 | Implement `src/evidence_routing/policies.py::bm25_policy`, `all_modules_policy`, `frozen_heuristic_policy`, and `oracle_policy`, including oracle abstention and routable-only cost/harm comparison masks. |  |  |
| TASK-045 | Implement `src/evidence_routing/models.py::fit_logistic_router` and `fit_xgboost_router` with frozen hyperparameters and one success-probability estimate per question-path pair. |  |  |
| TASK-046 | Implement `src/evidence_routing/calibration.py::fit_fold_calibrator`, `select_abstention_threshold`, `select_no_abstention_route`, and `apply_abstention_policy`; force all-fold abstention when no calibration threshold satisfies the frozen risk and minimum-decision constraints. |  |  |
| TASK-047 | Implement source-domain out-of-fold calibration and target-domain untouched evaluation in `src/evidence_routing/transfer.py::run_cross_domain_transfer`. |  |  |
| TASK-048 | Add `tests/test_features.py`, `tests/test_splits.py`, `tests/test_policies.py`, and `tests/test_calibration.py` covering route-time feature restrictions, group leakage, oracle non-routable handling, threshold selection, forced abstention, and unchanged outer-test application. |  |  |

Completion criteria:

- Primary router features require no downstream path execution.
- No document group crosses train, calibration, and test partitions.
- Threshold hashes and calibration-partition IDs are present in every test prediction artifact.
- Oracle non-routable questions cannot reduce Signal 3(b) or 3(c) cost/harm estimates.

### Implementation Phase 7: Evaluation and Automated Go/No-Go Decision

- GOAL-007: Produce all frozen metrics, uncertainty estimates, transfer results, and decision signals from immutable artifacts.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-049 | Implement `src/evidence_routing/metrics.py` for evidence completeness, harmful expansion, combined path success, Recall@k, MRR, coverage, accepted risk, abstention rate, Brier score, frozen-bin ECE, model calls, graph targets, context attachments, and runtime. |  |  |
| TASK-050 | Implement `src/evidence_routing/bootstrap.py::paired_bootstrap` with 10,000 question-level resamples and frozen seed `20260723`. |  |  |
| TASK-051 | Implement `src/evidence_routing/evaluation.py::run_within_domain`, `run_pooled_oof`, and `run_transfer_evaluation`; report all-question and accepted-decision denominators explicitly. |  |  |
| TASK-052 | Implement `src/evidence_routing/go_no_go.py::compute_signal_1` through `compute_signal_5`, `evaluate_qualitative_gates`, and `make_decision`; require all qualitative gates and at least four quantitative signals. |  |  |
| TASK-053 | Add `tests/test_metrics.py` and `tests/test_go_no_go.py` with boundary fixtures at 19.9%/20%, four/five module benefits, 4.9/5 percentage-point gains, 19.9/20% cost reduction, two/three favorable folds, and 19.9/20% coverage. |  |  |
| TASK-054 | Run the complete frozen Pilot evaluation from a clean checkout and write aggregate, per-domain, fold-level, transfer, and policy artifacts under `artifacts/pilot-v1/`. |  |  |
| TASK-055 | Generate `docs/results/pilot-v1-feasibility-report.md` containing evidence for every qualitative gate and quantitative signal, execution failures, limitations, and the final `GO` or `NO-GO` decision. |  |  |

Completion criteria:

- All metrics reproduce from frozen inputs with one command.
- Signal calculations include numerators, denominators, thresholds, and pass/fail values.
- Signal 5 uses only calibration-selected fold thresholds applied unchanged to outer tests.
- The final decision is generated from the frozen rules and is not manually overridden.

### Implementation Phase 8: Release and Handoff

- GOAL-008: Publish a privacy-safe, reproducible Pilot record and define the next authorized project boundary.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-056 | Update `README.md` with exact environment setup, local adapter configuration, Pilot command sequence, data-availability limits, and result summary. |  |  |
| TASK-057 | Create `LICENSE` after the owner selects a license; default recommendation is Apache-2.0 for code, with data and manuscript materials governed separately. |  |  |
| TASK-058 | Run unit tests, integration tests, linting, privacy scan, schema validation, manifest verification, and a clean-checkout reproduction test. |  |  |
| TASK-059 | Tag the frozen protocol commit `pilot-v1-protocol`, tag the completed result commit `pilot-v1-results`, and push tags only after every release check passes. |  |  |
| TASK-060 | If the decision is `GO`, create a separate full-dataset implementation plan; if `NO-GO`, archive the Pilot evidence and create a separate Plan B design only after explicit approval. |  |  |

Completion criteria:

- The GitHub repository contains no restricted data and passes the privacy scan.
- A clean environment reproduces the Go/No-Go report from permitted artifacts.
- The next phase is not started without a new approved plan.

## 3. Alternatives

- **ALT-001**: Train a neural Transformer router. Rejected for the Pilot because 120 questions are insufficient to justify the complexity and the contribution is task definition, calibration, and transfer rather than architecture scale.
- **ALT-002**: Evaluate every combination of reranking, context, and graph modules. Rejected because six frozen paths already support the required stage-level comparisons and additional combinations increase annotation cost.
- **ALT-003**: Evaluate generated answers and claim-level factuality. Rejected because it requires a separate answer and claim annotation study and risks conflating retrieval sufficiency with generation faithfulness.
- **ALT-004**: Start with multimodal table retrieval. Deferred as Plan B because it requires new image/cell annotations and materially larger compute and engineering effort.
- **ALT-005**: Build a generic retrieval platform or web interface. Rejected as unrelated to the Pilot decision.

## 4. Dependencies

- **DEP-001**: Read-only access to the chemical-safety project referenced by `CER_CHEMICAL_PROJECT_ROOT`.
- **DEP-002**: Read-only access to the pharmaceutical-regulatory project referenced by `CER_PHARMA_PROJECT_ROOT`.
- **DEP-003**: Access to the frozen Neo4j or export state used by the chemical-safety study.
- **DEP-004**: Access to the frozen pharmaceutical document and graph exports used by the second study.
- **DEP-005**: Local availability of the frozen reranker checkpoint selected in `configs/reranker-v1.yaml`.
- **DEP-006**: One second reviewer for exactly 30 complete Pilot questions.
- **DEP-007**: Python 3.11 or later and sufficient local compute to rerank BM25 top-50 candidates.
- **DEP-008**: Explicit owner decision on the repository code license before TASK-057.

## 5. Files

- **FILE-001**: `README.md` - public project overview, setup, and status.
- **FILE-002**: `.gitignore` - restricted-data and local-environment exclusions.
- **FILE-003**: `pyproject.toml` - Python package and tool configuration.
- **FILE-004**: `configs/local.example.yaml` - safe local configuration template.
- **FILE-005**: `configs/pilot-v1.yaml` - frozen Pilot parameters and decision thresholds.
- **FILE-006**: `configs/cues-v1.yaml` - frozen multilingual heuristic cues.
- **FILE-007**: `configs/reranker-v1.yaml` - immutable reranker configuration.
- **FILE-008**: `src/evidence_routing/schemas.py` - canonical data contracts.
- **FILE-009**: `src/evidence_routing/adapters/` - two read-only domain adapters.
- **FILE-010**: `src/evidence_routing/paths.py` - six path implementations.
- **FILE-011**: `src/evidence_routing/annotation.py` - blinded export, import, agreement, and adjudication support.
- **FILE-012**: `src/evidence_routing/models.py` - Logistic Regression and XGBoost routers.
- **FILE-013**: `src/evidence_routing/calibration.py` - calibration and abstention.
- **FILE-014**: `src/evidence_routing/evaluation.py` - within-domain, pooled, and transfer evaluation.
- **FILE-015**: `src/evidence_routing/go_no_go.py` - frozen decision computation.
- **FILE-016**: `docs/annotation/` - question and evidence annotation manuals.
- **FILE-017**: `docs/protocol/` - source inventory and frozen protocol.
- **FILE-018**: `docs/results/pilot-v1-feasibility-report.md` - final Pilot decision report.
- **FILE-019**: `data/schemas/` and `data/templates/` - public schemas and safe examples.
- **FILE-020**: `tests/` - deterministic unit, contract, leakage, and decision-boundary tests.

## 6. Testing

- **TEST-001**: Validate every committed schema example and reject missing provenance or invalid path IDs.
- **TEST-002**: Verify stable BM25 and reranker tie ordering across repeated fixture runs.
- **TEST-003**: Verify P0-P5 output ordering, cutoffs, sidecars, graph filtering, and deduplication.
- **TEST-004**: Verify a downstream-path exception cannot alter another path's output.
- **TEST-005**: Detect document-group leakage across training, calibration, and test folds.
- **TEST-006**: Reject primary features that require downstream path execution.
- **TEST-007**: Verify exactly 30 full questions are selected for duplicate annotation.
- **TEST-008**: Verify corpus insufficiency requires a manual-check record.
- **TEST-009**: Verify calibration and threshold fitting never access outer-test labels or predictions.
- **TEST-010**: Verify forced abstention when no calibration threshold satisfies both risk and minimum accepted-count constraints.
- **TEST-011**: Verify no-abstention fallback chooses maximum probability and resolves ties by lexicographic cost.
- **TEST-012**: Verify oracle non-routable questions are excluded from Signal 3(b) and 3(c) comparisons.
- **TEST-013**: Verify every Go/No-Go boundary immediately below, at, and above its frozen threshold.
- **TEST-014**: Verify tracked files contain no prohibited path, secret, raw-corpus, database, or private-review artifact.
- **TEST-015**: Reproduce the final feasibility report from a clean checkout and permitted local inputs.

## 7. Risks & Assumptions

- **RISK-001**: One fixed path may dominate all others, invalidating the routing premise. Mitigation: enforce the Pilot Go/No-Go gate before dataset expansion.
- **RISK-002**: Construction-category cues may make routing artificially easy. Mitigation: include frozen counter-cue cases and keep categories out of model inputs.
- **RISK-003**: Chinese-English transfer may measure language shift more than domain shift. Mitigation: emphasize rank-derived features and report the limitation explicitly.
- **RISK-004**: The prior projects may expose incompatible identifiers or unavailable live services. Mitigation: complete the read-only source-system inventory before adapter implementation.
- **RISK-005**: HARMFUL judgments may have low agreement. Mitigation: use ordered criteria, examples, complete-question duplicate annotation, and preserved adjudication.
- **RISK-006**: The calibration partitions may be too small to produce a valid threshold. Mitigation: force and report full abstention without using test data to repair coverage.
- **RISK-007**: Reranker compute may be slow on local hardware. Mitigation: cache immutable top-50 reranker scores and keep exactly one frozen model.
- **RISK-008**: Restricted source passages may leak through annotations or logs. Mitigation: separate private authoring artifacts, serialize only permitted identifiers, and run the privacy scanner.
- **ASSUMPTION-001**: Both existing projects retain stable source identifiers and enough provenance to create cross-path evidence specifications.
- **ASSUMPTION-002**: The chemical and pharmaceutical corpora can be accessed read-only during Pilot execution.
- **ASSUMPTION-003**: A second reviewer can complete all evidence labels for the selected 30 questions.
- **ASSUMPTION-004**: The publication target does not require a different template or experimental claim before the Pilot decision.

## 8. Related Specifications / Further Reading

- `docs/superpowers/specs/2026-07-23-pilot-first-evidence-routing-design.md`
- `docs/protocol/pilot-v1.md` after TASK-015
- `docs/annotation/question-construction-v1.md` after TASK-031
- `docs/annotation/evidence-labeling-v1.md` after TASK-032
