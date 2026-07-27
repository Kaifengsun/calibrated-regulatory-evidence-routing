"""Frozen, auditable Pilot Go/No-Go signal calculations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from evidence_routing.evaluation import OOFDecision
from evidence_routing.metrics import PathOutcome
from evidence_routing.policies import RouteDecision, derive_path_costs, oracle_policy


@dataclass(frozen=True)
class SignalResult:
    signal_id: str
    passed: bool
    measurements: dict[str, Any]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _outcome_map(outcomes: Sequence[PathOutcome]) -> dict[tuple[str, str], PathOutcome]:
    result = {(row.question_id, row.path_id): row for row in outcomes}
    if len(result) != len(outcomes):
        raise ValueError("path outcomes must be unique")
    return result


def compute_signal_1(outcomes: Sequence[PathOutcome]) -> SignalResult:
    rows = _outcome_map(outcomes)
    question_ids = sorted({row.question_id for row in outcomes})
    rescued = [
        question_id
        for question_id in question_ids
        if not rows[(question_id, "P0")].combined_path_success
        and any(rows[(question_id, f"P{index}")].combined_path_success for index in range(1, 6))
    ]
    fraction = len(rescued) / len(question_ids)
    return SignalResult(
        "signal_1",
        fraction >= 0.20,
        {"rescued_count": len(rescued), "denominator": len(question_ids), "fraction": fraction},
    )


def compute_signal_2(outcomes: Sequence[PathOutcome]) -> SignalResult:
    rows = _outcome_map(outcomes)
    question_ids = sorted({row.question_id for row in outcomes})
    comparisons = {
        "reranking": [("P0", "P1")],
        "context": [("P0", "P2"), ("P1", "P4")],
        "graph": [("P0", "P3"), ("P4", "P5")],
    }
    counts = {}
    for module, pairs in comparisons.items():
        rescued = {
            question_id
            for question_id in question_ids
            if any(
                not rows[(question_id, before)].combined_path_success
                and rows[(question_id, after)].combined_path_success
                for before, after in pairs
            )
        }
        counts[module] = len(rescued)
    qualifying = sum(value >= 5 for value in counts.values())
    return SignalResult(
        "signal_2",
        qualifying >= 2,
        {"module_rescue_counts": counts, "qualifying_module_count": qualifying},
    )


def compute_signal_3(outcomes: Sequence[PathOutcome]) -> SignalResult:
    rows = _outcome_map(outcomes)
    oracle = oracle_policy(outcomes)
    question_count = len(oracle)
    routable = [row for row in oracle if row.routable]
    oracle_success_rate = len(routable) / question_count
    p0_success_rate = (
        sum(rows[(row.question_id, "P0")].combined_path_success for row in oracle) / question_count
    )
    condition_a = oracle_success_rate - p0_success_rate >= 0.05
    costs = derive_path_costs(outcomes)
    oracle_neural = sum(costs[row.selected_path_id].neural_model_calls for row in routable) / len(
        routable
    )
    p5_neural = sum(costs["P5"].neural_model_calls for _ in routable) / len(routable)
    p5_success = sum(rows[(row.question_id, "P5")].combined_path_success for row in routable) / len(
        routable
    )
    condition_b = 1.0 - p5_success >= -0.02 and 1 - oracle_neural / p5_neural >= 0.20
    oracle_harm = sum(
        rows[(row.question_id, row.selected_path_id)].harmful_expansion for row in routable
    ) / len(routable)
    p5_harm = sum(rows[(row.question_id, "P5")].harmful_expansion for row in routable) / len(
        routable
    )
    oracle_complete = sum(
        rows[(row.question_id, row.selected_path_id)].evidence_complete for row in routable
    ) / len(routable)
    p5_complete = sum(rows[(row.question_id, "P5")].evidence_complete for row in routable) / len(
        routable
    )
    condition_c = p5_harm - oracle_harm >= 0.05 and oracle_complete - p5_complete >= -0.02
    return SignalResult(
        "signal_3",
        condition_a or condition_b or condition_c,
        {
            "routable_count": len(routable),
            "oracle_success_rate_all": oracle_success_rate,
            "p0_success_rate_all": p0_success_rate,
            "oracle_mean_neural_calls_routable": oracle_neural,
            "p5_mean_neural_calls_routable": p5_neural,
            "p5_success_rate_routable": p5_success,
            "oracle_harm_rate_routable": oracle_harm,
            "p5_harm_rate_routable": p5_harm,
            "oracle_completeness_routable": oracle_complete,
            "p5_completeness_routable": p5_complete,
            "condition_a": condition_a,
            "condition_b": condition_b,
            "condition_c": condition_c,
        },
    )


def compute_signal_4(
    oof: Sequence[OOFDecision],
    heuristic: Sequence[RouteDecision],
    outcomes: Sequence[PathOutcome],
) -> SignalResult:
    rows = _outcome_map(outcomes)
    heuristic_by_question = {row.question_id: row for row in heuristic}
    costs = derive_path_costs(outcomes)
    learned_rate = sum(row.no_abstention_success for row in oof) / len(oof)
    heuristic_success = {
        row.question_id: rows[(row.question_id, row.selected_path_id)].combined_path_success
        for row in heuristic
    }
    heuristic_rate = sum(heuristic_success.values()) / len(heuristic_success)
    learned_calls = sum(costs[row.no_abstention_path_id].neural_model_calls for row in oof) / len(
        oof
    )
    heuristic_calls = sum(
        costs[row.selected_path_id].neural_model_calls for row in heuristic
    ) / len(heuristic)
    success_folds = 0
    call_folds = 0
    for fold in range(5):
        fold_rows = [row for row in oof if row.fold == fold]
        learned_fold = sum(row.no_abstention_success for row in fold_rows) / len(fold_rows)
        heuristic_fold = sum(heuristic_success[row.question_id] for row in fold_rows) / len(
            fold_rows
        )
        success_folds += learned_fold > heuristic_fold
        learned_fold_calls = sum(
            costs[row.no_abstention_path_id].neural_model_calls for row in fold_rows
        ) / len(fold_rows)
        heuristic_fold_calls = sum(
            costs[heuristic_by_question[row.question_id].selected_path_id].neural_model_calls
            for row in fold_rows
        ) / len(fold_rows)
        call_folds += learned_fold_calls < heuristic_fold_calls
    condition_a = learned_rate - heuristic_rate >= 0.05 and success_folds >= 3
    cost_reduction = 0.0 if heuristic_calls == 0 else 1 - learned_calls / heuristic_calls
    condition_b = (
        learned_rate - heuristic_rate >= -0.02 and cost_reduction >= 0.20 and call_folds >= 3
    )
    return SignalResult(
        "signal_4",
        condition_a or condition_b,
        {
            "model_id": oof[0].model_id,
            "learned_success_rate": learned_rate,
            "heuristic_success_rate": heuristic_rate,
            "favorable_success_folds": success_folds,
            "learned_mean_neural_calls": learned_calls,
            "heuristic_mean_neural_calls": heuristic_calls,
            "neural_call_reduction_fraction": cost_reduction,
            "favorable_call_folds": call_folds,
            "condition_a": condition_a,
            "condition_b": condition_b,
        },
    )


def compute_signal_5(oof: Sequence[OOFDecision]) -> SignalResult:
    accepted = [row for row in oof if not row.abstained]
    coverage = len(accepted) / len(oof)
    accepted_risk = (
        1 - sum(row.combined_path_success for row in accepted) / len(accepted) if accepted else None
    )
    unselective_risk = 1 - sum(row.no_abstention_success for row in oof) / len(oof)
    reduction = None if accepted_risk is None else unselective_risk - accepted_risk
    passed = (
        coverage >= 0.20
        and accepted_risk is not None
        and accepted_risk <= 0.10
        and reduction >= 0.05
    )
    return SignalResult(
        "signal_5",
        passed,
        {
            "model_id": oof[0].model_id,
            "accepted_count": len(accepted),
            "denominator": len(oof),
            "coverage": coverage,
            "accepted_failure_rate": accepted_risk,
            "no_abstention_failure_rate": unselective_risk,
            "risk_reduction": reduction,
        },
    )


def make_decision(
    qualitative_gates: Mapping[str, bool], signals: Sequence[SignalResult]
) -> dict[str, Any]:
    quantitative_passes = sum(signal.passed for signal in signals)
    all_qualitative = len(qualitative_gates) == 3 and all(qualitative_gates.values())
    return {
        "decision": "GO" if all_qualitative and quantitative_passes >= 4 else "NO-GO",
        "all_qualitative_gates_passed": all_qualitative,
        "quantitative_signals_passed": quantitative_passes,
        "required_quantitative_signals": 4,
    }


def evaluate_qualitative_gates(
    no_fixed_route_dominates: bool,
    annotation_distinctions_reliable: bool,
    route_differences_nontrivial: bool,
) -> dict[str, bool]:
    """Record the three inspection gates without inventing numeric proxies."""
    return {
        "no_single_fixed_route_trivially_dominates_quality_and_cost": (no_fixed_route_dominates),
        "annotations_distinguish_complete_failure_and_insufficiency": (
            annotation_distinctions_reliable
        ),
        "route_differences_survive_artifact_and_lexical_inspection": (route_differences_nontrivial),
    }
