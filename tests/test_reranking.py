import math

import pytest

from evidence_routing.adapters.base import RetrievalCandidate, SourceSection
from evidence_routing.reranking import direct_candidates, rank_with_scores
from evidence_routing.schemas import Domain


def _candidate(source_id: str, rank: int, score: float = 1.0) -> RetrievalCandidate:
    return RetrievalCandidate(
        section=SourceSection(
            domain=Domain.CHEMICAL,
            source_id=source_id,
            document_id="STD-DEMO",
            heading=f"Heading {source_id}",
            content="Fictional evidence.",
            source_type="section",
            runtime_locator=f"runtime:{source_id}",
            provenance={"locator": f"fixture:{source_id}"},
            reranker_text=f"Heading {source_id}\nFictional evidence.",
        ),
        rank=rank,
        score=score,
    )


def test_rank_with_scores_uses_frozen_tie_break() -> None:
    candidates = [_candidate("S-B", 1), _candidate("S-A", 2), _candidate("S-C", 3)]
    ranked = rank_with_scores(candidates, [0.5, 0.5, 0.9])
    assert [row.candidate.section.source_id for row in ranked] == ["S-C", "S-B", "S-A"]
    assert [row.reranker_score for row in ranked] == [0.9, 0.5, 0.5]


@pytest.mark.parametrize("score", [-0.1, 1.1, math.inf, math.nan])
def test_rank_with_scores_rejects_invalid_probability(score: float) -> None:
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        rank_with_scores([_candidate("S-A", 1)], [score])


def test_rank_with_scores_requires_one_score_per_candidate() -> None:
    with pytest.raises(ValueError, match="score count mismatch"):
        rank_with_scores([_candidate("S-A", 1)], [])


def test_direct_candidates_preserves_bm25_order_without_neural_score() -> None:
    candidates = [_candidate("S-A", 1), _candidate("S-B", 2)]
    rows = direct_candidates(candidates)
    assert [row.candidate for row in rows] == candidates
    assert all(row.reranker_score is None for row in rows)
