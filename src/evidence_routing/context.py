"""Deterministic context sidecars for the frozen top-five seeds."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from evidence_routing.adapters.base import ContextItem, RegulatoryCorpusAdapter
from evidence_routing.reranking import ScoredCandidate
from evidence_routing.schemas import ContextType

_CONTEXT_ORDER = {
    ContextType.HEADING_PATH: 0,
    ContextType.IMMEDIATE_PARENT: 1,
    ContextType.TABLE: 2,
}


@dataclass(frozen=True, slots=True)
class AttachedContext:
    seed_rank: int
    item: ContextItem


def attach_context(
    adapter: RegulatoryCorpusAdapter,
    seeds: Sequence[ScoredCandidate],
    *,
    query_text: str,
) -> tuple[AttachedContext, ...]:
    """Attach at most three ordered sidecars to each of the first five seeds."""
    del query_text  # Reserved for frozen cue metadata; direct attachments are eligible.
    attached: list[AttachedContext] = []
    seen_context_ids: set[str] = set()
    for seed_rank, scored in enumerate(seeds[:5], 1):
        source_id = scored.candidate.section.source_id
        rows = adapter.get_context_sidecars(source_id, include_table=True)
        eligible: list[ContextItem] = []
        for item in rows:
            if item.seed_source_id != source_id:
                raise ValueError(
                    f"context seed mismatch: expected={source_id} actual={item.seed_source_id}"
                )
            if item.context_type not in _CONTEXT_ORDER:
                raise ValueError(f"unsupported context type: {item.context_type}")
            if not item.context_id or not item.source_id or not item.document_id:
                raise ValueError("context item lacks stable identity")
            if item.context_id in seen_context_ids:
                continue
            eligible.append(item)
        eligible.sort(
            key=lambda item: (
                _CONTEXT_ORDER[item.context_type],
                item.source_id,
                item.context_id,
            )
        )
        for item in eligible[:3]:
            seen_context_ids.add(item.context_id)
            attached.append(AttachedContext(seed_rank=seed_rank, item=item))
    return tuple(attached)
