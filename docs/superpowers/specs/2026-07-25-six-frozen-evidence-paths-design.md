# Six Frozen Evidence Paths: Modular Stage Design

Date approved: 2026-07-25

Status: approved design, pending implementation

## 1. Objective and boundary

Phase 4 implements the six already frozen evidence paths without changing the
Pilot research protocol. BM25 runs once to depth 50. Reusable stages then
rerank, attach context, or expand graph relations in the combinations specified
for `P0` through `P5`.

This phase includes fixture-level tests, a real reranker smoke test, and a small
live smoke test in each domain. It does not construct or run the formal
120-question Pilot, train a router, add paths, tune path rules from labels, or
introduce a general workflow engine.

## 2. Chosen architecture

The implementation uses modular stage composition:

- `reranking.py` owns the frozen neural reranking contract;
- `context.py` owns ordered sidecar attachment;
- `graph.py` owns bounded one-hop graph insertion;
- `paths.py` composes the stages into the six fixed paths;
- `runner.py` runs BM25 once, isolates path failures, and emits public schemas.

This keeps the stage-level ablations explicit while avoiding duplicated logic
inside six independent path implementations. A configurable DAG or plugin
framework is out of scope.

## 3. Reranking stage

`FrozenReranker` accepts the query and the complete BM25 top-50 candidate list.
The production implementation loads the exact model snapshot and prompt
specified in `configs/reranker-v1.yaml`. Test doubles implement the same narrow
interface without loading a model.

The payload is Unicode-normalized and bounded exactly as specified in the
frozen reranker configuration. The output must contain one score in `[0, 1]`
for every supplied candidate. Candidates are ordered by:

1. reranker score descending;
2. original BM25 rank ascending;
3. stable `source_id` ascending.

No candidate is added or removed before the requested top-k truncation.
Loading failures, malformed score vectors, non-finite scores, or unavailable
frozen model files are explicit execution errors.

## 4. Context stage

Context is requested only for the first five seeds of the stage input. The
stage delegates source resolution to the domain adapter but revalidates and
sorts returned items so adapter implementation details cannot change the frozen
path behavior.

Within each seed, sidecars are ordered by:

1. heading path;
2. immediate parent;
3. table;
4. stable context identifier as final tie-break.

At most three sidecars attach to one seed. Sidecars keep independent source and
provenance identifiers and never consume a ranked top-10 position. The current
adapter contract only exposes directly attached tables; therefore every table
returned by the adapter meets the direct-attachment branch of the frozen
eligibility rule. Query cue detection is retained as recorded metadata but does
not manufacture or infer a table attachment.

## 5. Graph stage

Graph expansion uses the first five seeds, follows one outgoing hop, and accepts
only normalized `CITES` or `DEPENDS_ON` relations with confidence at least
`0.85`.

Eligible targets are ordered by:

1. source seed rank ascending;
2. edge confidence descending;
3. normalized relation type ascending;
4. target stable `source_id` ascending.

The five seeds remain at the front. Up to five unique graph targets are then
inserted. Targets duplicating any preserved seed, previously inserted graph
target, or later direct candidate are represented only once. Remaining ranked
positions are filled from the direct list in its existing order until the
top-10 cutoff is reached.

Every graph result preserves the original relation type, normalized type,
confidence, and seed identifier. The stage does not infer missing relations or
perform additional hops.

## 6. Six path compositions

| Path | Composition |
|---|---|
| `P0` | BM25 top 10 |
| `P1` | BM25 top 50, rerank, top 10 |
| `P2` | BM25 top 10, context on first five BM25 seeds |
| `P3` | BM25 top 10, graph from first five BM25 seeds |
| `P4` | BM25 top 50, rerank to direct top 10, context on first five reranked seeds |
| `P5` | BM25 top 50, rerank to direct top 10, context and graph from the same first five reranked seeds |

`P5` computes and freezes its five reranked seeds before either downstream
stage. Context attachment cannot change graph seeds, and graph insertion cannot
change which items receive context.

## 7. Output conversion and provenance

Stage-internal records retain source text only in memory for model input and
adapter operations. Public `RankedEvidenceUnit` and `ContextSidecar` records
contain identifiers, scores, relation metadata, and provenance but not copied
source text.

Direct units retain original BM25 rank and score. Reranked direct units also
carry the reranker score. Graph units carry their seed and relation fields.
Ranks are recomputed consecutively after the final path composition.

Each `PathRun` records:

- completion or a stable path-level error code;
- ranked and sidecar records;
- neural model calls;
- inserted graph-target count;
- attached context-item count;
- rounded non-negative runtime in milliseconds.

## 8. Runner behavior and errors

`run_all_paths` receives one validated `QueryRecord`, one domain adapter, and
one reranker. It calls `run_bm25_once` exactly once and reuses the immutable
first-stage result for all six paths.

Paths execute independently after the shared first stage. A downstream failure
produces an `execution_error` `PathRun` for that path and does not mutate or
cancel another path. If the shared BM25 call itself fails, all six paths receive
a stable first-stage error because none can execute.

Test doubles may inject failures to verify isolation. Unexpected exception text
is not copied into public artifacts; public records use bounded stable error
codes.

## 9. Verification

Fixture tests cover:

- byte-stable repeated outputs;
- BM25 reuse exactly once;
- all six compositions;
- reranker tie-breaking and score validation;
- top-five seed selection;
- context ordering and three-per-seed bound;
- sidecars not occupying ranks;
- graph confidence filtering, ordering, deduplication, and five-target bound;
- top-10 truncation and consecutive ranks;
- `P5` use of the same frozen seed set;
- path-level error isolation;
- public schema validation and provenance fields.

After fixture tests pass, smoke verification loads the locally frozen Qwen
reranker and runs a very small number of chemical and pharmaceutical queries.
Smoke outputs are diagnostic only and cannot be used to change the frozen path
logic. Formal 120-question execution remains in Phase 5.

## 10. Completion criteria

Phase 4 is complete when:

1. all stage and path tests pass;
2. repeated fixture runs serialize identically apart from measured runtime;
3. the real reranker snapshot is verified and completes a bounded inference;
4. each domain completes at least one live six-path smoke run;
5. privacy scanning confirms that no source text, credentials, model files, or
   machine-local paths are tracked;
6. the implementation and verification evidence are committed before formal
   Pilot path labels exist.
