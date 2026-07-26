"""Deployable, pre-execution feature construction for route prediction."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from evidence_routing.policies import PathCost, normalize_for_cues

_FORBIDDEN_DOWNSTREAM_KEYS = {
    "reranker_score",
    "reranker_agreement",
    "executed_overlap",
    "retrieved_target_properties",
    "ranked_units",
    "context_sidecars",
}


def _gap(scores: Sequence[float], position: int) -> float:
    if len(scores) <= position:
        return 0.0
    return (scores[0] - scores[position]) / max(abs(scores[0]), 1e-9)


def _score_entropy(scores: Sequence[float]) -> float:
    if not scores:
        return 0.0
    maximum = max(scores)
    weights = [math.exp(score - maximum) for score in scores]
    total = sum(weights)
    return -sum((weight / total) * math.log(weight / total) for weight in weights)


def build_route_time_features(
    query: Mapping[str, Any],
    bm25_scores: Sequence[float],
    bounded_graph_metadata: Mapping[str, float | int],
    path_costs: Mapping[str, PathCost],
    cues: Mapping[str, Sequence[str]],
) -> list[dict[str, float | int | str]]:
    """Return one deployable feature row per path after BM25 only.

    ``bounded_graph_metadata`` may contain only metadata such as eligible edge
    counts and maximum stored confidence; it must not contain fetched target
    text or attributes.  Path outcomes and all later stages are deliberately
    absent from this interface.
    """
    forbidden = _FORBIDDEN_DOWNSTREAM_KEYS & set(query) | _FORBIDDEN_DOWNSTREAM_KEYS & set(
        bounded_graph_metadata
    )
    if forbidden:
        raise ValueError(f"route-time features cannot use downstream fields: {sorted(forbidden)}")
    if len(bm25_scores) < 2:
        raise ValueError("route-time features require at least two BM25 scores")
    text = normalize_for_cues(str(query["query_text"]))
    table_cues = [normalize_for_cues(value) for value in cues["table_context"]]
    relation_cues = [normalize_for_cues(value) for value in cues["citation_dependency"]]
    shared: dict[str, float | int | str] = {
        "question_id": str(query["question_id"]),
        "domain": str(query["domain"]),
        "query_length": len(text),
        "bm25_top_score": float(bm25_scores[0]),
        "bm25_gap_1_2": _gap(bm25_scores, 1),
        "bm25_gap_1_5": _gap(bm25_scores, 4),
        "bm25_top10_entropy": _score_entropy(bm25_scores[:10]),
        "has_table_context_cue": int(any(cue in text for cue in table_cues)),
        "has_citation_dependency_cue": int(any(cue in text for cue in relation_cues)),
        "eligible_outgoing_edge_count": int(
            bounded_graph_metadata.get("eligible_outgoing_edge_count", 0)
        ),
        "max_edge_confidence": float(bounded_graph_metadata.get("max_edge_confidence", 0.0)),
    }
    rows = []
    for path_id, cost in sorted(path_costs.items()):
        rows.append(
            shared
            | {
                "path_id": path_id,
                "cost_neural_calls": cost.neural_model_calls,
                "cost_graph_targets": cost.graph_targets_inserted,
                "cost_context_items": cost.context_items_attached,
                "cost_median_runtime_ms": cost.median_runtime_ms,
            }
        )
    return rows
