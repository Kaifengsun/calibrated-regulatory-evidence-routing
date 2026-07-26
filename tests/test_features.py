import pytest

from evidence_routing.features import build_route_time_features
from evidence_routing.policies import PathCost


def test_route_time_features_are_pre_execution_only() -> None:
    rows = build_route_time_features(
        {"question_id": "Q1", "domain": "chemical", "query_text": "table cite"},
        [10.0, 9.0, 8.0, 7.0, 6.0],
        {"eligible_outgoing_edge_count": 2, "max_edge_confidence": 0.9},
        {"P0": PathCost(0, 0, 0, 1, "P0")},
        {"table_context": ["table"], "citation_dependency": ["cite"]},
    )
    assert rows[0]["has_table_context_cue"] == 1
    assert rows[0]["cost_neural_calls"] == 0
    with pytest.raises(ValueError, match="downstream"):
        build_route_time_features(
            {"question_id": "Q1", "domain": "chemical", "query_text": "x", "reranker_score": 1},
            [1.0, 0.9], {}, {"P0": PathCost(0, 0, 0, 1, "P0")},
            {"table_context": [], "citation_dependency": []},
        )
