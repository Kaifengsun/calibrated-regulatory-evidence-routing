"""Single-run BM25 normalization shared by all evidence paths."""

from __future__ import annotations

from dataclasses import dataclass

from evidence_routing.adapters.base import (
    CorpusManifest,
    RegulatoryCorpusAdapter,
    RetrievalCandidate,
)
from evidence_routing.schemas import QueryRecord


@dataclass(frozen=True, slots=True)
class FirstStageResult:
    question_id: str
    query: str
    manifest: CorpusManifest
    candidates: tuple[RetrievalCandidate, ...]


def run_bm25_once(
    adapter: RegulatoryCorpusAdapter,
    query: QueryRecord,
    *,
    depth: int = 50,
) -> FirstStageResult:
    """Run BM25 once and reject unstable or incomplete adapter output."""
    if depth != 50:
        raise ValueError("the frozen Pilot requires BM25 depth 50")
    manifest = adapter.corpus_manifest()
    if manifest.domain != query.domain:
        raise ValueError(
            f"query domain {query.domain.value} does not match adapter "
            f"domain {manifest.domain.value}"
        )
    candidates = adapter.bm25_search(query.query_text, limit=depth)
    if len(candidates) > depth:
        raise ValueError("adapter returned more candidates than requested")
    ranks = [row.rank for row in candidates]
    if ranks != list(range(1, len(ranks) + 1)):
        raise ValueError(f"BM25 ranks must be consecutive: {ranks}")
    source_ids = [row.section.source_id for row in candidates]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("BM25 candidates contain duplicate stable source IDs")
    if any(row.section.domain != query.domain for row in candidates):
        raise ValueError("BM25 candidates contain a cross-domain record")
    return FirstStageResult(
        question_id=query.question_id,
        query=query.query_text,
        manifest=manifest,
        candidates=tuple(candidates),
    )
