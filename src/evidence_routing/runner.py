"""One-first-stage runner with isolated execution of all frozen paths."""

from __future__ import annotations

from collections.abc import Callable

from evidence_routing.adapters.base import RegulatoryCorpusAdapter
from evidence_routing.paths import run_p0, run_p1, run_p2, run_p3, run_p4, run_p5
from evidence_routing.reranking import Reranker
from evidence_routing.retrieval import run_bm25_once
from evidence_routing.schemas import ExecutionStatus, PathId, PathRun, QueryRecord

_PATH_IDS = tuple(PathId)
_NEURAL_PATHS = {PathId.P1, PathId.P4, PathId.P5}


def _error_run(
    query: QueryRecord,
    path_id: PathId,
    error_code: str,
) -> PathRun:
    return PathRun(
        run_id=f"RUN-{query.question_id}-{path_id.value}",
        question_id=query.question_id,
        path_id=path_id,
        status=ExecutionStatus.EXECUTION_ERROR,
        ranked_units=[],
        context_sidecars=[],
        error_code=error_code,
        neural_model_calls=int(path_id in _NEURAL_PATHS),
        graph_targets_inserted=0,
        context_items_attached=0,
        runtime_ms=0,
    )


def run_all_paths(
    adapter: RegulatoryCorpusAdapter,
    query: QueryRecord,
    reranker: Reranker,
) -> tuple[PathRun, ...]:
    """Run BM25 once, then execute and isolate exactly P0 through P5."""
    try:
        first_stage = run_bm25_once(adapter, query)
    except Exception:
        return tuple(
            _error_run(query, path_id, "E_FIRST_STAGE")
            for path_id in _PATH_IDS
        )

    functions: dict[PathId, Callable[[], PathRun]] = {
        PathId.P0: lambda: run_p0(first_stage),
        PathId.P1: lambda: run_p1(first_stage, reranker),
        PathId.P2: lambda: run_p2(first_stage, adapter),
        PathId.P3: lambda: run_p3(first_stage, adapter),
        PathId.P4: lambda: run_p4(first_stage, adapter, reranker),
        PathId.P5: lambda: run_p5(first_stage, adapter, reranker),
    }
    runs: list[PathRun] = []
    for path_id in _PATH_IDS:
        try:
            runs.append(functions[path_id]())
        except Exception:
            runs.append(_error_run(query, path_id, f"E_{path_id.value}_EXECUTION"))
    return tuple(runs)
