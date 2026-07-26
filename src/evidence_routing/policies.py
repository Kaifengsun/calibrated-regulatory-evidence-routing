"""Frozen non-learned route-selection policies for the Pilot."""

from __future__ import annotations

import statistics
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from evidence_routing.metrics import PathOutcome


@dataclass(frozen=True)
class PathCost:
    """Static path cost used for deterministic lexicographic selection."""

    neural_model_calls: int
    graph_targets_inserted: float
    context_items_attached: float
    median_runtime_ms: float
    path_id: str

    @property
    def tuple(self) -> tuple[int, float, float, float, str]:
        return (
            self.neural_model_calls,
            self.graph_targets_inserted,
            self.context_items_attached,
            self.median_runtime_ms,
            self.path_id,
        )


@dataclass(frozen=True)
class RouteDecision:
    """A selected path, or a documented evidence-sufficiency abstention."""

    question_id: str
    policy_id: str
    selected_path_id: str | None
    abstained: bool
    routable: bool | None = None

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def derive_path_costs(outcomes: Sequence[PathOutcome]) -> dict[str, PathCost]:
    """Derive frozen path profiles from all executed paths, never labels alone."""
    by_path: dict[str, list[PathOutcome]] = defaultdict(list)
    for outcome in outcomes:
        by_path[outcome.path_id].append(outcome)
    costs: dict[str, PathCost] = {}
    for path_id, rows in by_path.items():
        neural_calls = {row.neural_model_calls for row in rows}
        if len(neural_calls) != 1:
            raise ValueError(f"path has non-static neural call cost: {path_id}")
        costs[path_id] = PathCost(
            neural_model_calls=neural_calls.pop(),
            graph_targets_inserted=statistics.median(
                row.graph_targets_inserted for row in rows
            ),
            context_items_attached=statistics.median(
                row.context_items_attached for row in rows
            ),
            median_runtime_ms=statistics.median(row.runtime_ms for row in rows),
            path_id=path_id,
        )
    return costs


def bm25_policy(question_ids: Sequence[str]) -> list[RouteDecision]:
    """Select the frozen BM25-only baseline P0 for every question."""
    return [
        RouteDecision(question_id, "bm25", "P0", abstained=False)
        for question_id in question_ids
    ]


def all_modules_policy(question_ids: Sequence[str]) -> list[RouteDecision]:
    """Select the frozen full-composition baseline P5 for every question."""
    return [
        RouteDecision(question_id, "all_modules", "P5", abstained=False)
        for question_id in question_ids
    ]


def normalize_for_cues(text: str) -> str:
    """Apply the cue-file's frozen Unicode/case/space normalization."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def normalized_bm25_ambiguity_gap(scores: Sequence[float], epsilon: float = 1e-9) -> float:
    """Return the frozen top-two normalized BM25 ambiguity gap."""
    if len(scores) < 2:
        raise ValueError("at least two BM25 scores are required")
    return (scores[0] - scores[1]) / max(abs(scores[0]), epsilon)


def frozen_heuristic_policy(
    queries: Sequence[Mapping[str, Any]],
    cues: Mapping[str, Sequence[str]],
    *,
    ambiguity_gap_threshold: float = 0.15,
) -> list[RouteDecision]:
    """Apply the protocol-frozen multilingual cue precedence with no abstention."""
    table_cues = tuple(normalize_for_cues(cue) for cue in cues["table_context"])
    citation_cues = tuple(normalize_for_cues(cue) for cue in cues["citation_dependency"])
    decisions: list[RouteDecision] = []
    for query in queries:
        text = normalize_for_cues(str(query["query_text"]))
        has_table = any(cue in text for cue in table_cues)
        has_citation = any(cue in text for cue in citation_cues)
        gap = normalized_bm25_ambiguity_gap(query["bm25_scores"])
        if has_table and has_citation:
            path_id = "P5"
        elif has_citation:
            path_id = "P3"
        elif has_table:
            path_id = "P2"
        elif gap < ambiguity_gap_threshold:
            path_id = "P1"
        else:
            path_id = "P0"
        decisions.append(
            RouteDecision(str(query["question_id"]), "frozen_heuristic", path_id, False)
        )
    return decisions


def oracle_policy(
    outcomes: Sequence[PathOutcome],
    costs: Mapping[str, PathCost] | None = None,
) -> list[RouteDecision]:
    """Choose each routable question's lowest-cost successful path; else abstain."""
    static_costs = dict(costs or derive_path_costs(outcomes))
    by_question: dict[str, list[PathOutcome]] = defaultdict(list)
    for outcome in outcomes:
        by_question[outcome.question_id].append(outcome)
    decisions: list[RouteDecision] = []
    for question_id, rows in sorted(by_question.items()):
        successful = [row for row in rows if row.combined_path_success]
        if not successful:
            decisions.append(RouteDecision(question_id, "oracle", None, True, routable=False))
            continue
        chosen = min(successful, key=lambda row: static_costs[row.path_id].tuple)
        decisions.append(
            RouteDecision(question_id, "oracle", chosen.path_id, False, routable=True)
        )
    return decisions
