---
goal: Implement the Six Frozen Evidence Paths with Modular Stages
version: 1.0
date_created: 2026-07-25
last_updated: 2026-07-25
owner: Kaifeng Sun
status: 'In progress'
tags: [feature, retrieval, reranking, evidence-routing, pilot]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

This plan implements the approved modular execution design for `P0` through
`P5`. It ends after fixture verification and bounded live smoke tests. It does
not execute the formal 120-question Pilot.

## 1. Requirements & Constraints

- **REQ-001**: Call `run_bm25_once` exactly once per `QueryRecord` at depth 50.
- **REQ-002**: Implement exactly `P0` through `P5` from
  `configs/pilot-v1.yaml`; do not add configurable paths.
- **REQ-003**: Evaluate no more than ten ranked evidence units per path.
- **REQ-004**: Preserve the first five direct seeds in graph-expanded paths.
- **REQ-005**: Attach context only to the first five seeds, with at most three
  sidecars per seed in heading, parent, table order.
- **REQ-006**: Follow only one outgoing `CITES` or `DEPENDS_ON` edge with
  confidence at least `0.85`, inserting at most five unique graph targets.
- **REQ-007**: Use reranker score descending, BM25 rank ascending, and stable
  source ID ascending as the reranking order.
- **REQ-008**: Use the exact same five reranked seeds for context and graph in
  `P5`.
- **REQ-009**: Emit only existing version-1 `PathRun`, `RankedEvidenceUnit`, and
  `ContextSidecar` public schemas.
- **REQ-010**: Isolate downstream path failures with stable public error codes.
- **CON-001**: Do not construct or execute formal Pilot questions in this plan.
- **CON-002**: Do not add a DAG engine, plugin framework, new route, neural
  router, multi-hop expansion, or multimodal table processing.
- **CON-003**: Do not commit source text, model files, credentials, absolute
  local paths, or live smoke outputs containing restricted content.
- **GUD-001**: Keep stage interfaces small and independently fixture-testable.
- **GUD-002**: Treat adapters and frozen YAML files as authoritative inputs.
- **PAT-001**: Represent immutable intermediate rankings with frozen
  dataclasses and tuples.
- **PAT-002**: Convert internal records to public Pydantic schemas only at the
  path boundary.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Implement deterministic stage primitives without loading a real
  neural model in tests.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `src/evidence_routing/reranking.py` with `Reranker` protocol, immutable scored-candidate record, score-vector validation, frozen sorting, and a production `QwenFrozenReranker` with lazy optional imports. |  |  |
| TASK-002 | Create `src/evidence_routing/context.py` with `attach_context(adapter, seeds, query_text)` enforcing five seeds, context-type order, stable tie-break, and three-sidecar cap. |  |  |
| TASK-003 | Create `src/evidence_routing/graph.py` with `expand_one_hop(adapter, direct_candidates, seeds)` enforcing confidence `0.85`, frozen target order, global deduplication, five-target cap, preserved seeds, direct remainder fill, and top-10 cutoff. |  |  |
| TASK-004 | Create focused fixture tests in `tests/test_reranking.py` and `tests/test_stages.py`; use deterministic test doubles and no real source data. |  |  |

Completion criteria:

- Stage tests pass without model downloads or live services.
- Invalid reranker scores and adapter outputs fail deterministically.
- Context and graph output order is byte-stable on repeated fixture runs.

### Implementation Phase 2

- GOAL-002: Compose and serialize all six fixed paths.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Create `src/evidence_routing/paths.py` with explicit `run_p0` through `run_p5` functions and shared conversion helpers for public ranked units and context sidecars. |  |  |
| TASK-006 | Ensure direct units preserve BM25 rank/score, reranked units preserve reranker score, and graph units preserve complete seed/relation provenance. |  |  |
| TASK-007 | Create `tests/test_paths.py` covering all six compositions, consecutive ranks, top-10 cutoff, sidecar placement, graph insertion, and identical `P5` seed use. |  |  |

Completion criteria:

- All six path functions return schema-valid `PathRun` objects.
- Repeated fixture execution differs only in measured runtime.
- No path mutates the shared first-stage result.

### Implementation Phase 3

- GOAL-003: Execute all paths from one first-stage result with isolated errors.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-008 | Create `src/evidence_routing/runner.py::run_all_paths` to call BM25 once, execute paths independently, map exceptions to stable bounded error codes, and return runs ordered `P0` through `P5`. |  |  |
| TASK-009 | Replace the phase-gated `run-paths` CLI registration with a callable command boundary only after the runner contract is implemented; retain explicit refusal when required local inputs are absent. |  |  |
| TASK-010 | Create `tests/test_runner.py` proving one BM25 call, six ordered outputs, path failure isolation, and all-path first-stage failure handling. |  |  |

Completion criteria:

- One fixture question produces six ordered public path records.
- A failure in one downstream stage does not alter another completed path.
- A first-stage failure produces six explicit errors and no downstream calls.

### Implementation Phase 4

- GOAL-004: Verify the real frozen reranker and both live adapters without
  creating formal Pilot artifacts.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | Locate and verify the local Qwen3-Reranker snapshot against the frozen manifest SHA-256 without copying model files into the repository. |  |  |
| TASK-012 | Run one bounded real reranker inference over redistribution-safe or transient live candidates; record only aggregate pass/fail and timing. |  |  |
| TASK-013 | Run at least one transient six-path smoke query through the chemical adapter and one through the pharmaceutical adapter; inspect counts, order, and provenance without committing source text. |  |  |
| TASK-014 | Run `pytest`, `ruff check .`, configuration validation, schema validation, and tracked-file privacy scanning; update this plan's task statuses and README current status. |  |  |

Completion criteria:

- The frozen model snapshot passes identity verification and bounded inference.
- Both domains complete a transient live six-path run or record a specific
  external dependency blocker.
- All offline quality gates pass and no restricted artifact is tracked.

## 3. Alternatives

- **ALT-001**: Implement six independent path functions with duplicated stage
  logic. Rejected because duplicated sorting and truncation rules can drift.
- **ALT-002**: Implement a generic DAG or configuration-driven pipeline.
  Rejected because six paths are permanently fixed for this Pilot.
- **ALT-003**: Mock the reranker for the entire phase. Rejected because the
  approved completion boundary requires one bounded real-model smoke test.

## 4. Dependencies

- **DEP-001**: Existing `RegulatoryCorpusAdapter` implementations and frozen
  corpus manifests.
- **DEP-002**: Existing `QueryRecord`, `PathRun`, `RankedEvidenceUnit`, and
  `ContextSidecar` schemas.
- **DEP-003**: Frozen `configs/pilot-v1.yaml`,
  `configs/reranker-v1.yaml`, and `configs/cues-v1.yaml`.
- **DEP-004**: Locally accessible Qwen3-Reranker snapshot and its installed
  PyTorch/Transformers-compatible runtime for the live smoke test.
- **DEP-005**: Read-only chemical Neo4j and pharmaceutical snapshot access for
  transient live verification.

## 5. Files

- **FILE-001**: `src/evidence_routing/reranking.py`
- **FILE-002**: `src/evidence_routing/context.py`
- **FILE-003**: `src/evidence_routing/graph.py`
- **FILE-004**: `src/evidence_routing/paths.py`
- **FILE-005**: `src/evidence_routing/runner.py`
- **FILE-006**: `src/evidence_routing/cli.py`
- **FILE-007**: `tests/test_reranking.py`
- **FILE-008**: `tests/test_stages.py`
- **FILE-009**: `tests/test_paths.py`
- **FILE-010**: `tests/test_runner.py`
- **FILE-011**: `README.md`
- **FILE-012**: `plan/feature-six-evidence-paths-1.md`

## 6. Testing

- **TEST-001**: Validate reranker cardinality, finite probability range, ties,
  and deterministic output.
- **TEST-002**: Validate context seed cap, type order, stable ID tie-break, and
  per-seed sidecar cap.
- **TEST-003**: Validate graph relation filter, confidence threshold, ordering,
  deduplication, target cap, and direct remainder.
- **TEST-004**: Validate exact `P0` through `P5` compositions and public schema
  conversion.
- **TEST-005**: Validate BM25 single execution and failure isolation.
- **TEST-006**: Validate real frozen reranker snapshot and one bounded
  inference.
- **TEST-007**: Validate one transient six-path live run per domain.
- **TEST-008**: Run full regression, lint, configuration, and privacy gates.

## 7. Risks & Assumptions

- **RISK-001**: The local reranker runtime may be unavailable or incompatible
  with the frozen bfloat16 configuration. The implementation must report this
  as a smoke-test blocker and must not silently change precision.
- **RISK-002**: Live services may be offline. Offline fixture completion remains
  valid, but Phase 4 is not marked complete until the blocker is resolved or
  explicitly documented.
- **RISK-003**: Runtime measurement is nondeterministic. Tests compare semantic
  output separately from `runtime_ms`.
- **RISK-004**: Adapter output may contain duplicate or malformed context/graph
  records. Stage validation must fail or deterministically deduplicate according
  to the frozen rule.
- **ASSUMPTION-001**: `Section.uid` and pharmaceutical `chunk_id` remain stable
  across the frozen snapshots.
- **ASSUMPTION-002**: Adapter graph results already normalize relation semantics
  but the graph stage still validates normalized type and confidence.

## 8. Related Specifications / Further Reading

- `docs/superpowers/specs/2026-07-25-six-frozen-evidence-paths-design.md`
- `docs/superpowers/specs/2026-07-23-pilot-first-evidence-routing-design.md`
- `docs/protocol/pilot-v1.md`
- `configs/pilot-v1.yaml`
- `configs/reranker-v1.yaml`
- `configs/cues-v1.yaml`
