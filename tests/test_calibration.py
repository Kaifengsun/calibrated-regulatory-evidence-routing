from evidence_routing.calibration import (
    apply_abstention_policy,
    select_abstention_threshold,
    select_no_abstention_route,
)
from evidence_routing.policies import PathCost


def _costs():
    return {"P0": PathCost(0, 0, 0, 1, "P0"), "P1": PathCost(1, 0, 0, 1, "P1")}


def test_threshold_is_selected_from_calibration_and_applied_unchanged():
    probabilities = {f"Q{i}": {"P0": 0.9, "P1": 0.1} for i in range(10)}
    outcomes = {
        (question, path): path == "P0" for question in probabilities for path in ("P0", "P1")
    }
    selection = select_abstention_threshold(probabilities, outcomes, _costs())
    assert selection.threshold == 0.1 and not selection.force_abstain
    applied = apply_abstention_policy({"T1": {"P0": 0.05, "P1": 0.02}}, _costs(), selection)
    assert applied[0].abstained


def test_forced_abstention_and_no_abstention_fallback():
    probabilities = {"Q1": {"P0": 0.2, "P1": 0.1}}
    forced = select_abstention_threshold(
        probabilities, {("Q1", "P0"): False, ("Q1", "P1"): False}, _costs()
    )
    assert forced.force_abstain
    assert apply_abstention_policy(probabilities, _costs(), forced)[0].abstained
    assert select_no_abstention_route(probabilities, _costs(), 0.9)[0].selected_path_id == "P0"
