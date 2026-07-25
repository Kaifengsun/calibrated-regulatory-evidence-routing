---
goal: Build and Validate the Twenty-Question Pre-Freeze Authoring Batch
version: 1.0
date_created: 2026-07-25
last_updated: 2026-07-25
owner: Kaifeng Sun
status: 'In progress'
tags: [process, data, annotation, pilot, regulatory-retrieval]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

This plan implements the approved evidence-first, path-blind workflow for a
20-question pre-freeze batch. It stops after the questions have been reviewed,
frozen, executed through `P0` to `P5`, and exported for blinded evidence
annotation. It does not construct the remaining 100 Pilot questions or train a
router.

## 1. Requirements & Constraints

- **REQ-001**: Produce exactly 10 chemical-safety and 10 pharmaceutical
  candidates.
- **REQ-002**: Produce exactly two candidates per domain for each of
  `direct_clause`, `parent_heading_context`, `table_related`,
  `citation_dependency`, and `evidence_insufficient`.
- **REQ-003**: Represent every candidate with one version-1 `QueryRecord` and
  one version-1 `EvidenceSpecification`.
- **REQ-004**: Resolve every non-insufficiency evidence identifier against the
  frozen domain corpus before review export.
- **REQ-005**: Require a documented manual negative search before accepting
  any `evidence_insufficient` candidate.
- **REQ-006**: Prevent authors from inspecting `P0` to `P5` results until the
  corresponding question and evidence specification are frozen.
- **REQ-007**: Reject normalized question duplicates within the new batch and
  against the locally supplied prior-manuscript question inventory.
- **REQ-008**: Preserve immutable question, specification, path, rank, source,
  and sidecar identities across review export and import.
- **REQ-009**: Execute all six frozen paths only for accepted and frozen
  questions.
- **REQ-010**: Keep source excerpts, review workbooks, freeze mappings, and
  corpus-insufficiency search notes outside version control.
- **SEC-001**: Do not commit credentials, machine-local paths, copyrighted
  source text, private reviewer identities, or model files.
- **CON-001**: Do not add a web interface, LLM judge, multimodal extraction,
  router training, calibration, or new retrieval paths.
- **CON-002**: Do not automatically assign construction categories from query
  keywords or retrieval outcomes.
- **CON-003**: Do not silently revise a frozen question; a correction creates a
  new version and invalidates prior path outputs.
- **GUD-001**: Use CSV for compact machine-readable authoring manifests and
  XLSX only for human review workbooks.
- **GUD-002**: Keep candidate selection, validation, freezing, and workbook
  handling as separate modules with fixture-testable interfaces.
- **PAT-001**: Use deterministic ordering by domain, construction category,
  question ID, path ID, rank, and sidecar order.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Freeze the human rules and local authoring contract before
  selecting live candidates.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `docs/annotation/question-construction-v1.md` containing the 2-by-5 batch quota, evidence-first/path-blind sequence, category definitions, counter-cue requirements, prior-question non-overlap procedure, review checklist, and accept/revise/reject decisions. | ✅ | 2026-07-25 |
| TASK-002 | Create `docs/annotation/evidence-labeling-v1.md` containing the five labels, completeness logic, HARMFUL decision order, corpus-insufficiency manual-search procedure, and positive/negative examples for both domains. | ✅ | 2026-07-25 |
| TASK-003 | Create `data/templates/authoring-record.example.json`, `data/templates/manual-search-record.example.json`, and their Pydantic models in `src/evidence_routing/authoring.py`; export matching version-1 JSON schemas under `data/schemas/`. | ✅ | 2026-07-25 |
| TASK-004 | Add `tests/test_authoring.py` to validate record identity, review-state transitions, manual-search requirements, and rejection of committed source excerpts or local paths. | ✅ | 2026-07-25 |

Completion criteria:

- Both manuals define every decision needed by an author or reviewer.
- Safe templates validate against committed generated schemas.
- Insufficiency acceptance without a completed manual search fails.

### Implementation Phase 2

- GOAL-002: Discover balanced candidate evidence structures without observing
  route performance.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Create `src/evidence_routing/candidate_selection.py` with read-only selectors for direct, context, table, and citation evidence structures; selectors return stable identifiers and private excerpt handles but never execute `run_all_paths`. | ✅ | 2026-07-25 |
| TASK-006 | Restrict chemical selection to the frozen 399-standard allowlist and pharmaceutical selection to the frozen 2,478-chunk manifest; verify corpus hashes and source revisions before selection. | ✅ | 2026-07-25 |
| TASK-007 | Add deterministic selector constraints for attributable non-empty evidence, eligible sidecars, one-hop normalized graph edges at confidence at least 0.85, source-group diversity, and duplicate removal. | ✅ | 2026-07-25 |
| TASK-008 | Add `tests/test_candidate_selection.py` with fixture adapters proving domain/category balance inputs, path-blind operation, stable ordering, graph threshold enforcement, and source-resolution failure handling. | ✅ | 2026-07-25 |
| TASK-009 | Run bounded live selection in each domain and write candidate structures only to the ignored `artifacts/private/authoring/pilot-20-v1/` directory. | ✅ | 2026-07-25 |

Completion criteria:

- Both domains yield at least two reviewable structures for each
  non-insufficiency category.
- No selector imports or invokes path execution.
- Live output contains no tracked source text.

Live result on 2026-07-25: chemical selection yielded five structures in every
non-insufficiency category. Pharmaceutical selection yielded five direct, five
parent/heading, five table, and zero citation-dependency structures. The
complete pharmaceutical normalized-edge index contains no target that resolves
uniquely to one attributable chunk under the frozen rule. The first completion
criterion is therefore not met, and Phase 3 must not begin until the protocol
decision is recorded.

### Implementation Phase 3

- GOAL-003: Author, validate, and review exactly 20 path-blind candidate
  questions.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Create a private 20-row authoring manifest with exactly two rows per domain-category cell; create matching `QueryRecord`, `EvidenceSpecification`, and `AuthoringRecord` files. |  |  |
| TASK-011 | Create `src/evidence_routing/question_validation.py::validate_authoring_batch` to enforce counts, language, ID uniqueness, normalized-text uniqueness, source groups, schema validity, evidence resolution, graph-edge eligibility, and manual-search records. |  |  |
| TASK-012 | Implement prior-question comparison using locally supplied normalized prior-question inventories; emit exact-match and high-overlap review flags without automatically rejecting semantic near-matches. |  |  |
| TASK-013 | Create `src/evidence_routing/review.py::export_prefreeze_review` and `import_prefreeze_review` using an XLSX workbook with immutable identity columns and explicit `accept`, `revise_and_review`, or `reject_and_replace` decisions. |  |  |
| TASK-014 | Add `tests/test_question_validation.py` and `tests/test_review.py` covering quotas, duplicates, unresolved evidence, immutable workbook fields, deterministic ordering, and review-state transitions. |  |  |
| TASK-015 | Export the first review workbook for Kaifeng Sun; do not freeze or run paths until all 20 rows receive an accepted review decision. |  |  |

Completion criteria:

- The private batch contains exactly 20 schema-valid candidates with the
  approved balance.
- Review import detects any changed immutable identity.
- Every candidate has an explicit review outcome.

### Implementation Phase 4

- GOAL-004: Freeze accepted questions and prepare blinded path evidence for
  annotation.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-016 | Create `src/evidence_routing/freeze.py::freeze_queries` to verify accepted review state, batch hashes, protocol/config hashes, corpus hashes, counts, quotas, and prior-question checks before writing immutable private frozen records. |  |  |
| TASK-017 | Add a correction ledger that invalidates prior run hashes whenever a frozen question version changes; prohibit in-place overwrite of a frozen batch. |  |  |
| TASK-018 | Execute `run_all_paths` for all 20 frozen questions and record exactly 120 `PathRun` records, allowing only explicit path-level execution errors. |  |  |
| TASK-019 | Create `src/evidence_routing/annotation.py::export_blinded_workbook` with randomized method-blinded packages and a separate ignored immutable identity mapping. |  |  |
| TASK-020 | Create `annotation.py::import_reviewed_workbook` to validate immutable identities and produce version-1 evidence annotations without overwriting raw reviewer labels. |  |  |
| TASK-021 | Add `tests/test_freeze.py` and `tests/test_annotation.py` covering no-overwrite behavior, frozen hashes, correction invalidation, 120-run count, blinding, deterministic randomization, and identity tampering. |  |  |
| TASK-022 | Run regression, lint, configuration validation, schema validation, tracked-file privacy scanning, and bounded live smoke checks; update this plan and the main Pilot plan without marking human review tasks complete prematurely. |  |  |

Completion criteria:

- Exactly 20 accepted questions and 120 path records are frozen privately.
- Public tracked outputs contain only redistribution-safe metadata.
- A blinded evidence workbook can complete a lossless export/import round trip.
- All automated quality and privacy gates pass.

## 3. Alternatives

- **ALT-001**: Write all 120 questions immediately. Rejected because category
  constructibility and review workload have not yet been validated.
- **ALT-002**: Generate questions automatically with an LLM and accept them
  after superficial screening. Rejected because evidence grounding and
  category validity require human judgment.
- **ALT-003**: Build a web annotation application. Rejected because an XLSX
  workflow is sufficient for a bounded 20-question batch.
- **ALT-004**: Run the six paths during candidate authoring to find questions
  with desirable differences. Rejected because this would leak system behavior
  into dataset construction.

## 4. Dependencies

- **DEP-001**: Approved design
  `docs/superpowers/specs/2026-07-25-pilot-question-authoring-and-annotation-design.md`.
- **DEP-002**: Frozen protocol in `configs/pilot-v1.yaml` and
  `docs/protocol/pilot-v1.md`.
- **DEP-003**: Existing version-1 query, evidence, path, and annotation schemas.
- **DEP-004**: Existing read-only chemical and pharmaceutical adapters.
- **DEP-005**: Existing modular `P0` through `P5` runner.
- **DEP-006**: Local spreadsheet runtime capable of reading and writing XLSX.
- **DEP-007**: Human review by Kaifeng Sun before freeze.

## 5. Files

- **FILE-001**: `docs/annotation/question-construction-v1.md`
- **FILE-002**: `docs/annotation/evidence-labeling-v1.md`
- **FILE-003**: `src/evidence_routing/authoring.py`
- **FILE-004**: `src/evidence_routing/candidate_selection.py`
- **FILE-005**: `src/evidence_routing/question_validation.py`
- **FILE-006**: `src/evidence_routing/review.py`
- **FILE-007**: `src/evidence_routing/freeze.py`
- **FILE-008**: `src/evidence_routing/annotation.py`
- **FILE-009**: `tests/test_authoring.py`
- **FILE-010**: `tests/test_candidate_selection.py`
- **FILE-011**: `tests/test_question_validation.py`
- **FILE-012**: `tests/test_review.py`
- **FILE-013**: `tests/test_freeze.py`
- **FILE-014**: `tests/test_annotation.py`
- **FILE-015**: `data/templates/authoring-record.example.json`
- **FILE-016**: `data/templates/manual-search-record.example.json`
- **FILE-017**: `data/schemas/authoring-record-v1.schema.json`
- **FILE-018**: `data/schemas/manual-search-record-v1.schema.json`

## 6. Testing

- **TEST-001**: Validate authoring and manual-search schema invariants.
- **TEST-002**: Prove candidate selection cannot execute or inspect paths.
- **TEST-003**: Validate two-per-domain-category quotas and deterministic order.
- **TEST-004**: Validate source, sidecar, and graph-edge resolution.
- **TEST-005**: Validate exact and high-overlap prior-question flags.
- **TEST-006**: Validate pre-freeze workbook identity preservation.
- **TEST-007**: Validate immutable freeze hashes and no-overwrite behavior.
- **TEST-008**: Validate blinded evidence export/import and mapping separation.
- **TEST-009**: Run the full Pytest and Ruff suites.
- **TEST-010**: Run configuration, schema, and tracked-file privacy checks.
- **TEST-011**: Run bounded live selector checks in both frozen domains.
- **TEST-012**: Run all six paths on the accepted frozen batch only.

## 7. Risks & Assumptions

- **RISK-001**: Some domain-category cells may yield few defensible candidates.
  The selector may surface additional structures, but quotas cannot be relaxed
  without a protocol amendment.
- **RISK-002**: Table text may be absent or poorly attributable in one domain.
  Image extraction remains excluded; weak table candidates are rejected.
- **RISK-003**: A corpus-insufficiency claim can be expensive to verify.
  Candidate acceptance waits for a documented manual search.
- **RISK-004**: Prior-manuscript question inventories may not yet exist in a
  machine-readable local format. Exact freeze waits for the inventories;
  candidate discovery may proceed without them.
- **RISK-005**: Spreadsheet software may rewrite formatting or formulas.
  Imports use immutable identity values rather than workbook formatting.
- **ASSUMPTION-001**: The frozen chemical allowlist and both corpus snapshots
  remain accessible and unchanged.
- **ASSUMPTION-002**: Kaifeng Sun can judge question realism and complete the
  pre-freeze review.
- **ASSUMPTION-003**: A second annotator is not required for this 20-question
  workflow-validation batch; duplicate annotation remains mandatory for the
  later frozen 120-question Pilot.

## 8. Related Specifications / Further Reading

- `docs/superpowers/specs/2026-07-25-pilot-question-authoring-and-annotation-design.md`
- `docs/superpowers/specs/2026-07-23-pilot-first-evidence-routing-design.md`
- `docs/protocol/pilot-v1.md`
- `plan/process-end-to-end-pilot-1.md`
- `configs/pilot-v1.yaml`
