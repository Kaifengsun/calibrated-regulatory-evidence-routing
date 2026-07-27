from evidence_routing.metrics import PathOutcome
from evidence_routing.policies import (
    all_modules_policy,
    bm25_policy,
    derive_path_costs,
    frozen_heuristic_policy,
    normalized_bm25_ambiguity_gap,
    oracle_policy,
)


def _outcome(question_id: str, path_id: str, success: bool, calls: int = 0) -> PathOutcome:
    return PathOutcome(
        question_id=question_id,
        path_id=path_id,
        domain="chemical",
        evidence_complete=success,
        harmful_expansion=False,
        combined_path_success=success,
        required_found_count=0,
        required_total_count=0,
        sufficient_found=False,
        neural_model_calls=calls,
        graph_targets_inserted=0,
        context_items_attached=0,
        runtime_ms=10,
    )


def test_baseline_policies_are_fixed() -> None:
    assert [row.selected_path_id for row in bm25_policy(["Q1"])] == ["P0"]
    assert [row.selected_path_id for row in all_modules_policy(["Q1"])] == ["P5"]


def test_heuristic_precedence_and_ambiguity_boundary() -> None:
    cues = {"table_context": ["table"], "citation_dependency": ["cite"]}
    queries = [
        {"question_id": "Q1", "query_text": "cite a table", "bm25_scores": [10.0, 9.0]},
        {"question_id": "Q2", "query_text": "cite this", "bm25_scores": [10.0, 9.0]},
        {"question_id": "Q3", "query_text": "table only", "bm25_scores": [10.0, 9.0]},
        {"question_id": "Q4", "query_text": "plain", "bm25_scores": [10.0, 8.5]},
        {"question_id": "Q5", "query_text": "plain", "bm25_scores": [10.0, 8.6]},
    ]
    assert [row.selected_path_id for row in frozen_heuristic_policy(queries, cues)] == [
        "P5",
        "P3",
        "P2",
        "P0",
        "P1",
    ]
    assert normalized_bm25_ambiguity_gap([10.0, 8.5]) == 0.15


def test_oracle_abstains_when_no_path_succeeds_and_uses_lowest_cost() -> None:
    outcomes = [
        _outcome("Q1", "P0", False),
        _outcome("Q1", "P2", True),
        _outcome("Q1", "P1", True, calls=1),
        _outcome("Q2", "P0", False),
        _outcome("Q2", "P5", False, calls=1),
    ]
    decisions = {row.question_id: row for row in oracle_policy(outcomes)}
    assert decisions["Q1"].selected_path_id == "P2"
    assert decisions["Q1"].routable is True
    assert decisions["Q2"].abstained is True
    assert decisions["Q2"].routable is False


def test_cost_profiles_use_frozen_budgets_not_observed_insertions() -> None:
    outcome = _outcome("Q1", "P5", True, calls=1)
    costs = derive_path_costs([outcome])
    assert costs["P5"].graph_targets_inserted == 5
    assert costs["P5"].context_items_attached == 15
