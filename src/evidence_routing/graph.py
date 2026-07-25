"""Bounded one-hop graph insertion for the frozen evidence paths."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from evidence_routing.adapters.base import GraphTarget, RegulatoryCorpusAdapter
from evidence_routing.reranking import ScoredCandidate

_ELIGIBLE_RELATIONS = {"CITES", "DEPENDS_ON"}


@dataclass(frozen=True, slots=True)
class ExpandedItem:
    direct: ScoredCandidate | None
    graph: GraphTarget | None
    graph_seed: ScoredCandidate | None

    def __post_init__(self) -> None:
        if (self.direct is None) == (self.graph is None):
            raise ValueError("expanded item must contain exactly one evidence source")
        if self.graph is not None and self.graph_seed is None:
            raise ValueError("graph evidence requires its direct seed")
        if self.direct is not None and self.graph_seed is not None:
            raise ValueError("direct evidence cannot contain a graph seed")


def expand_one_hop(
    adapter: RegulatoryCorpusAdapter,
    direct_candidates: Sequence[ScoredCandidate],
    *,
    minimum_confidence: float = 0.85,
    maximum_targets: int = 5,
    cutoff: int = 10,
) -> tuple[ExpandedItem, ...]:
    """Preserve five seeds, insert graph targets, then fill from direct remainder."""
    if minimum_confidence != 0.85:
        raise ValueError("the frozen Pilot graph confidence is 0.85")
    if maximum_targets != 5 or cutoff != 10:
        raise ValueError("the frozen Pilot requires five graph targets and cutoff 10")
    if not direct_candidates:
        return ()
    seeds = tuple(direct_candidates[:5])
    seed_by_id = {
        row.candidate.section.source_id: row
        for row in seeds
    }
    if len(seed_by_id) != len(seeds):
        raise ValueError("graph seeds contain duplicate source IDs")
    direct_ids = {
        row.candidate.section.source_id
        for row in direct_candidates
    }
    if len(direct_ids) != len(direct_candidates):
        raise ValueError("direct graph input contains duplicate source IDs")

    targets = adapter.expand_graph(
        list(seed_by_id),
        minimum_confidence=minimum_confidence,
    )
    eligible: list[GraphTarget] = []
    for target in targets:
        if target.seed_source_id not in seed_by_id:
            raise ValueError(f"graph target refers to an unknown seed: {target.seed_source_id}")
        if target.relation_type_normalized not in _ELIGIBLE_RELATIONS:
            raise ValueError(
                f"unsupported normalized graph relation: {target.relation_type_normalized}"
            )
        if not 0.0 <= float(target.confidence) <= 1.0:
            raise ValueError("graph confidence must be in [0, 1]")
        if target.confidence < minimum_confidence:
            continue
        if not target.target.source_id:
            raise ValueError("graph target lacks stable identity")
        eligible.append(target)
    seed_rank = {
        row.candidate.section.source_id: index
        for index, row in enumerate(seeds, 1)
    }
    eligible.sort(
        key=lambda target: (
            seed_rank[target.seed_source_id],
            -float(target.confidence),
            target.relation_type_normalized,
            target.target.source_id,
        )
    )

    selected: list[GraphTarget] = []
    seen_targets: set[str] = set()
    for target in eligible:
        target_id = target.target.source_id
        if target_id in direct_ids or target_id in seen_targets:
            continue
        seen_targets.add(target_id)
        selected.append(target)
        if len(selected) == maximum_targets:
            break

    result: list[ExpandedItem] = [
        ExpandedItem(direct=row, graph=None, graph_seed=None)
        for row in seeds
    ]
    result.extend(
        ExpandedItem(
            direct=None,
            graph=target,
            graph_seed=seed_by_id[target.seed_source_id],
        )
        for target in selected
    )
    present = {
        row.direct.candidate.section.source_id
        for row in result
        if row.direct is not None
    } | {
        row.graph.target.source_id
        for row in result
        if row.graph is not None
    }
    for row in direct_candidates[5:]:
        if len(result) >= cutoff:
            break
        source_id = row.candidate.section.source_id
        if source_id in present:
            continue
        present.add(source_id)
        result.append(ExpandedItem(direct=row, graph=None, graph_seed=None))
    return tuple(result[:cutoff])
