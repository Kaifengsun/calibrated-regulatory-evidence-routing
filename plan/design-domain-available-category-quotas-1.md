---
goal: Implement Domain-Available Pilot Category Quotas
version: 1.0
date_created: 2026-07-25
last_updated: 2026-07-25
owner: Kaifeng Sun
status: 'In progress'
tags: [design, protocol, validation, pilot]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

This plan applies the approved pre-label quota amendment without changing the
120-question total, six evidence paths, or Go/No-Go thresholds.

## 1. Requirements & Constraints

- **REQ-001**: Store explicit quotas for all 10 domain-category cells.
- **REQ-002**: Require chemical quotas `[12, 12, 12, 12, 12]`.
- **REQ-003**: Require pharmaceutical quotas `[15, 15, 15, 0, 15]` in frozen
  category order.
- **REQ-004**: Store and validate the approved 20-question pre-freeze quotas.
- **REQ-005**: Store and validate the approved 30-question duplicate quotas.
- **REQ-006**: Reject pharmaceutical `citation_dependency` questions.
- **CON-001**: Do not add or infer pharmaceutical graph targets.
- **CON-002**: Do not change total questions, questions per domain, paths,
  labels, or Go/No-Go thresholds.
- **PAT-001**: Treat `configs/pilot-v1.yaml` as the machine-readable authority.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Synchronize every protocol and authoring document with the approved
  quota tables.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Replace scalar category quotas in `configs/pilot-v1.yaml` with explicit `question_quotas`, `prefreeze_question_quotas`, and `duplicate_annotation_quotas` mappings. |  |  |
| TASK-002 | Amend `docs/protocol/pilot-v1.md`, the two approved design specifications, and `docs/annotation/question-construction-v1.md` to reference the domain-available quotas. |  |  |
| TASK-003 | Update `plan/process-end-to-end-pilot-1.md` and `plan/process-pilot-question-authoring-1.md` without marking unexecuted human tasks complete. |  |  |

Completion criteria:

- All normative quota statements match the approved amendment.
- No normative document retains the obsolete per-domain five-category balance.

### Implementation Phase 2

- GOAL-002: Enforce the amended quotas in code and regression tests.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Replace the hard-coded 12-per-cell logic in `src/evidence_routing/validation.py::validate_query_dataset` with an explicit quota mapping parameter and a frozen default matching `configs/pilot-v1.yaml`. |  |  |
| TASK-005 | Update `tests/test_protocol.py` and dataset-validation tests to verify all full, pre-freeze, and duplicate quota totals and reject pharmaceutical citation questions. |  |  |
| TASK-006 | Run Pytest, Ruff, configuration validation, schema checks, and tracked-file privacy scanning; mark this plan completed. |  |  |

Completion criteria:

- A valid 120-question dataset passes with the amended quotas.
- Any pharmaceutical citation question or quota deviation fails deterministically.
- All quality and privacy gates pass.

## 3. Alternatives

- **ALT-001**: Resolve document-level pharmaceutical references heuristically.
  Rejected because target chunks are not uniquely attributable.
- **ALT-002**: Remove graph routing. Rejected because chemical graph evidence
  remains available and testable.
- **ALT-003**: Rebuild the pharmaceutical corpus. Rejected as disproportionate.

## 4. Dependencies

- **DEP-001**: Approved amendment specification.
- **DEP-002**: Frozen category enums and query schema.
- **DEP-003**: Existing dataset validation framework.

## 5. Files

- **FILE-001**: `configs/pilot-v1.yaml`
- **FILE-002**: `src/evidence_routing/validation.py`
- **FILE-003**: `tests/test_protocol.py`
- **FILE-004**: `docs/protocol/pilot-v1.md`
- **FILE-005**: `docs/annotation/question-construction-v1.md`
- **FILE-006**: Approved design and implementation plan documents.

## 6. Testing

- **TEST-001**: Verify full quota row and column totals.
- **TEST-002**: Verify pre-freeze and duplicate quota totals.
- **TEST-003**: Reject pharmaceutical citation-dependency records.
- **TEST-004**: Reject any domain-category count mismatch.
- **TEST-005**: Run full regression and privacy gates.

## 7. Risks & Assumptions

- **RISK-001**: Stale prose could retain obsolete quotas. Repository-wide text
  search is part of completion.
- **RISK-002**: Cross-domain transfer has no pharmaceutical positive graph
  examples; results must remain descriptive.
- **ASSUMPTION-001**: No Pilot question or path label has been frozen.

## 8. Related Specifications / Further Reading

- `docs/superpowers/specs/2026-07-25-domain-available-category-quotas-amendment-design.md`
- `docs/protocol/pilot-v1.md`
- `configs/pilot-v1.yaml`
