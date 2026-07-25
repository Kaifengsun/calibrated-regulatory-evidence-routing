"""Explicit composition of the six frozen Pilot evidence paths."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from evidence_routing.adapters.base import RegulatoryCorpusAdapter
from evidence_routing.context import AttachedContext, attach_context
from evidence_routing.graph import ExpandedItem, expand_one_hop
from evidence_routing.reranking import Reranker, ScoredCandidate, direct_candidates
from evidence_routing.retrieval import FirstStageResult
from evidence_routing.schemas import (
    ContextSidecar,
    ExecutionStatus,
    PathId,
    PathRun,
    RankedEvidenceUnit,
    UnitOrigin,
)
from evidence_routing.validation import validate_path_run


def _runtime_ms(started: float) -> int:
    return max(0, int(round((time.perf_counter() - started) * 1000.0)))


def _direct_unit(row: ScoredCandidate, rank: int) -> RankedEvidenceUnit:
    candidate = row.candidate
    section = candidate.section
    return RankedEvidenceUnit(
        source_id=section.source_id,
        document_id=section.document_id,
        domain=section.domain,
        source_type=section.source_type,
        rank=rank,
        origin=UnitOrigin.DIRECT,
        bm25_rank=candidate.rank,
        bm25_score=candidate.score,
        reranker_score=row.reranker_score,
        provenance=dict(section.provenance),
    )


def _expanded_unit(row: ExpandedItem, rank: int) -> RankedEvidenceUnit:
    if row.direct is not None:
        return _direct_unit(row.direct, rank)
    assert row.graph is not None
    assert row.graph_seed is not None
    target = row.graph
    seed = row.graph_seed.candidate
    provenance = {
        **target.target.provenance,
        **target.provenance,
        "bm25_fields_source": "graph_seed",
    }
    return RankedEvidenceUnit(
        source_id=target.target.source_id,
        document_id=target.target.document_id,
        domain=target.target.domain,
        source_type=target.target.source_type,
        rank=rank,
        origin=UnitOrigin.GRAPH,
        bm25_rank=seed.rank,
        bm25_score=seed.score,
        reranker_score=None,
        graph_seed_source_id=target.seed_source_id,
        relation_type_original=target.relation_type_original,
        relation_type_normalized=target.relation_type_normalized,
        relation_confidence=target.confidence,
        provenance=provenance,
    )


def _sidecars(
    attached: Sequence[AttachedContext],
    seeds: Sequence[ScoredCandidate],
) -> list[ContextSidecar]:
    seed_domain = {
        row.candidate.section.source_id: row.candidate.section.domain
        for row in seeds[:5]
    }
    order_by_seed: dict[str, int] = {}
    result: list[ContextSidecar] = []
    for row in attached:
        item = row.item
        order = order_by_seed.get(item.seed_source_id, 0) + 1
        order_by_seed[item.seed_source_id] = order
        try:
            domain = seed_domain[item.seed_source_id]
        except KeyError as error:
            raise ValueError(
                f"context output refers to unknown seed: {item.seed_source_id}"
            ) from error
        result.append(
            ContextSidecar(
                sidecar_id=item.context_id,
                seed_source_id=item.seed_source_id,
                seed_rank=row.seed_rank,
                source_id=item.source_id,
                document_id=item.document_id,
                domain=domain,
                context_type=item.context_type,
                order_within_seed=order,
                provenance=dict(item.provenance),
            )
        )
    return result


def _build_run(
    first_stage: FirstStageResult,
    path_id: PathId,
    ranked_units: list[RankedEvidenceUnit],
    context_sidecars: list[ContextSidecar],
    *,
    neural_model_calls: int,
    started: float,
) -> PathRun:
    run = PathRun(
        run_id=f"RUN-{first_stage.question_id}-{path_id.value}",
        question_id=first_stage.question_id,
        path_id=path_id,
        status=ExecutionStatus.COMPLETE,
        ranked_units=ranked_units,
        context_sidecars=context_sidecars,
        error_code=None,
        neural_model_calls=neural_model_calls,
        graph_targets_inserted=sum(
            unit.origin == UnitOrigin.GRAPH for unit in ranked_units
        ),
        context_items_attached=len(context_sidecars),
        runtime_ms=_runtime_ms(started),
    )
    validate_path_run(run)
    return run


def _reranked(
    first_stage: FirstStageResult,
    reranker: Reranker,
) -> tuple[ScoredCandidate, ...]:
    rows = reranker.rerank(first_stage.query, first_stage.candidates)
    if len(rows) != len(first_stage.candidates):
        raise ValueError("reranker must return every BM25 candidate")
    returned = [row.candidate.section.source_id for row in rows]
    expected = {row.section.source_id for row in first_stage.candidates}
    if len(returned) != len(set(returned)) or set(returned) != expected:
        raise ValueError("reranker output must be a permutation of BM25 candidates")
    return rows


def run_p0(first_stage: FirstStageResult) -> PathRun:
    started = time.perf_counter()
    rows = direct_candidates(first_stage.candidates[:10])
    units = [_direct_unit(row, rank) for rank, row in enumerate(rows, 1)]
    return _build_run(
        first_stage,
        PathId.P0,
        units,
        [],
        neural_model_calls=0,
        started=started,
    )


def run_p1(first_stage: FirstStageResult, reranker: Reranker) -> PathRun:
    started = time.perf_counter()
    rows = _reranked(first_stage, reranker)[:10]
    units = [_direct_unit(row, rank) for rank, row in enumerate(rows, 1)]
    return _build_run(
        first_stage,
        PathId.P1,
        units,
        [],
        neural_model_calls=1,
        started=started,
    )


def run_p2(
    first_stage: FirstStageResult,
    adapter: RegulatoryCorpusAdapter,
) -> PathRun:
    started = time.perf_counter()
    rows = direct_candidates(first_stage.candidates[:10])
    attached = attach_context(adapter, rows[:5], query_text=first_stage.query)
    units = [_direct_unit(row, rank) for rank, row in enumerate(rows, 1)]
    return _build_run(
        first_stage,
        PathId.P2,
        units,
        _sidecars(attached, rows),
        neural_model_calls=0,
        started=started,
    )


def run_p3(
    first_stage: FirstStageResult,
    adapter: RegulatoryCorpusAdapter,
) -> PathRun:
    started = time.perf_counter()
    rows = direct_candidates(first_stage.candidates[:10])
    expanded = expand_one_hop(adapter, rows)
    units = [_expanded_unit(row, rank) for rank, row in enumerate(expanded, 1)]
    return _build_run(
        first_stage,
        PathId.P3,
        units,
        [],
        neural_model_calls=0,
        started=started,
    )


def run_p4(
    first_stage: FirstStageResult,
    adapter: RegulatoryCorpusAdapter,
    reranker: Reranker,
) -> PathRun:
    started = time.perf_counter()
    rows = _reranked(first_stage, reranker)[:10]
    attached = attach_context(adapter, rows[:5], query_text=first_stage.query)
    units = [_direct_unit(row, rank) for rank, row in enumerate(rows, 1)]
    return _build_run(
        first_stage,
        PathId.P4,
        units,
        _sidecars(attached, rows),
        neural_model_calls=1,
        started=started,
    )


def run_p5(
    first_stage: FirstStageResult,
    adapter: RegulatoryCorpusAdapter,
    reranker: Reranker,
) -> PathRun:
    started = time.perf_counter()
    reranked = _reranked(first_stage, reranker)[:10]
    seeds = tuple(reranked[:5])
    attached = attach_context(adapter, seeds, query_text=first_stage.query)
    expanded = expand_one_hop(adapter, reranked)
    units = [_expanded_unit(row, rank) for rank, row in enumerate(expanded, 1)]
    return _build_run(
        first_stage,
        PathId.P5,
        units,
        _sidecars(attached, seeds),
        neural_model_calls=1,
        started=started,
    )


PathFunction = Callable[[], PathRun]
