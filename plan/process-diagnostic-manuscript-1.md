---
goal: Complete the approved diagnostic evidence-path study and English Word manuscript
version: 1.0
date_created: 2026-07-27
last_updated: 2026-07-27
owner: Kaifeng Sun
status: 'In progress'
tags: [research, evaluation, manuscript, regulatory-retrieval]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In_progress-yellow)

This plan converts the completed 120-question Pilot into the approved
diagnostic study without expanding the dataset or changing frozen results.

## 1. Requirements & Constraints

- **REQ-001**: Preserve all frozen Pilot questions, labels, paths, thresholds,
  folds, and Go/No-Go results.
- **REQ-002**: Report pooled, per-domain, fold-level, and transfer results.
- **REQ-003**: Generate 10,000 paired question-level bootstrap intervals using
  seed `20260723`.
- **REQ-004**: Deliver the final English manuscript as an editable `.docx`.
- **CON-001**: Do not create new questions, labels, retrieval paths, routers,
  or hyperparameter searches.
- **CON-002**: Do not select calibration thresholds on outer-test predictions.
- **CON-003**: Keep raw corpus content, private annotations, and question-level
  predictions out of tracked public files.
- **GUD-001**: Present negative calibration and Go/No-Go findings explicitly.
- **GUD-002**: Treat cross-domain transfer as descriptive because domain and
  language shift together.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Complete frozen statistical evaluation.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Implement `src/evidence_routing/bootstrap.py::paired_bootstrap` with 10,000 question-level resamples and seed `20260723`. | ✅ | 2026-07-27 |
| TASK-002 | Extend `src/evidence_routing/metrics.py` with Brier score, frozen-bin ECE, coverage, accepted risk, and abstention rate. | ✅ | 2026-07-27 |
| TASK-003 | Implement per-domain and construction-category diagnostic summaries in `src/evidence_routing/diagnostics.py`; prohibit category fields from model features. | ✅ | 2026-07-27 |
| TASK-004 | Implement descriptive two-direction transfer in `src/evidence_routing/transfer.py` with source-only fitting, calibration, and normalization. | ✅ | 2026-07-27 |
| TASK-005 | Add deterministic boundary, bootstrap, transfer-leakage, and metric tests under `tests/`. | ✅ | 2026-07-27 |

Completion criteria: all statistical outputs reproduce from frozen inputs and
all tests, formatting checks, and privacy scans pass.

### Implementation Phase 2

- GOAL-002: Freeze interpretable result artifacts and feasibility report.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Generate privacy-safe pooled, domain, stage, policy, calibration, transfer, and uncertainty manifests under `data/manifests/`. |  |  |
| TASK-007 | Generate publication tables under `artifacts/pilot-v1/tables/` from tracked aggregate manifests. |  |  |
| TASK-008 | Generate publication figures under `artifacts/pilot-v1/figures/` with accessible labels and consistent colors. |  |  |
| TASK-009 | Write `docs/results/pilot-v1-feasibility-report.md` with all three qualitative gates, five quantitative signals, limitations, and the frozen `NO-GO` expansion decision. |  |  |

Completion criteria: every reported number has a reproducible aggregate source
and the report does not overstate router or abstention performance.

### Implementation Phase 3

- GOAL-003: Produce and verify the English Word manuscript.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Verify current primary-source literature and create the manuscript bibliography with validated metadata. |  |  |
| TASK-011 | Draft the manuscript in full prose using the structure frozen in `docs/superpowers/specs/2026-07-27-diagnostic-evidence-path-study-design.md`. |  |  |
| TASK-012 | Generate `output/word/When_Does_Evidence_Expansion_Help.docx` with embedded tables and figures. |  |  |
| TASK-013 | Render the Word file to page images, inspect every page, and correct layout, captions, references, and pagination. |  |  |
| TASK-014 | Run a final claim-to-result audit, citation audit, privacy scan, and repository test suite. |  |  |

Completion criteria: the final editable Word manuscript is visually verified,
all claims match frozen results, and no private evidence text is embedded.

## 3. Alternatives

- **ALT-001**: Continue expanding the routing dataset. Rejected because the
  frozen Pilot passed only two of five quantitative continuation signals.
- **ALT-002**: Reframe the paper as context-only retrieval. Rejected because it
  discards useful path, harm, policy, and calibration evidence.
- **ALT-003**: Center the paper on calibration failure. Rejected because the
  broader evidence-path study is more balanced and suitable for the target
  publication level.
- **ALT-004**: Start multimodal table retrieval. Deferred because it requires a
  new annotation and engineering project.

## 4. Dependencies

- **DEP-001**: Frozen Pilot inputs under `artifacts/private/`.
- **DEP-002**: Aggregate manifests under `data/manifests/`.
- **DEP-003**: Python dependencies declared in `pyproject.toml`, including
  scikit-learn and XGBoost.
- **DEP-004**: Word-document tooling available through the Codex workspace
  runtime.

## 5. Files

- **FILE-001**: `docs/superpowers/specs/2026-07-27-diagnostic-evidence-path-study-design.md`.
- **FILE-002**: `src/evidence_routing/bootstrap.py`.
- **FILE-003**: `src/evidence_routing/metrics.py`.
- **FILE-004**: `src/evidence_routing/diagnostics.py`.
- **FILE-005**: `src/evidence_routing/transfer.py`.
- **FILE-006**: `docs/results/pilot-v1-feasibility-report.md`.
- **FILE-007**: `artifacts/pilot-v1/tables/`.
- **FILE-008**: `artifacts/pilot-v1/figures/`.
- **FILE-009**: `output/word/When_Does_Evidence_Expansion_Help.docx`.

## 6. Testing

- **TEST-001**: Verify bootstrap reproducibility and question-level paired
  resampling.
- **TEST-002**: Verify exact metric boundaries and explicit denominators.
- **TEST-003**: Verify source-domain transfer never fits target-domain data.
- **TEST-004**: Verify construction category is absent from model matrices.
- **TEST-005**: Verify all publication values match aggregate manifests.
- **TEST-006**: Verify the final Word file opens, renders, and contains no
  clipped tables, figures, or references.
- **TEST-007**: Verify tracked files pass the repository privacy scanner.

## 7. Risks & Assumptions

- **RISK-001**: The negative calibration result may weaken the original
  systems claim. Mitigation: center the paper on empirical path utility and
  report calibration as a boundary finding.
- **RISK-002**: Cross-domain differences may be confounded by language.
  Mitigation: label transfer results descriptive and avoid language-independent
  generalization claims.
- **RISK-003**: Some confidence intervals may be wide at 120 questions.
  Mitigation: report exact denominators, paired intervals, and effect sizes.
- **ASSUMPTION-001**: The target journal accepts an empirical diagnostic study
  rather than requiring a novel neural architecture.
- **ASSUMPTION-002**: The final journal template is not yet fixed; the Word
  manuscript will therefore use a clean generic academic layout.

## 8. Related Specifications / Further Reading

- `docs/superpowers/specs/2026-07-27-diagnostic-evidence-path-study-design.md`
- `docs/superpowers/specs/2026-07-23-pilot-first-evidence-routing-design.md`
- `docs/protocol/pilot-v1.md`
- `data/manifests/pilot-120-quantitative-signals-v1.json`
