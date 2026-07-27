from evidence_routing.go_no_go import (
    compute_signal_1,
    compute_signal_2,
    evaluate_qualitative_gates,
    make_decision,
)
from evidence_routing.metrics import PathOutcome


def _row(question: str, path: str, success: bool) -> PathOutcome:
    return PathOutcome(
        question,
        path,
        "chemical",
        success,
        False,
        success,
        0,
        0,
        False,
        int(path in {"P1", "P4", "P5"}),
        0,
        0,
        1,
    )


def _outcomes(rescued: int) -> list[PathOutcome]:
    rows = []
    for index in range(10):
        for path_index in range(6):
            rows.append(_row(f"Q{index}", f"P{path_index}", index < rescued and path_index == 2))
    return rows


def test_signal_1_boundary_is_inclusive() -> None:
    assert not compute_signal_1(_outcomes(1)).passed
    assert compute_signal_1(_outcomes(2)).passed


def test_signal_2_requires_two_modules_with_five_rescues() -> None:
    rows = []
    for index in range(10):
        for path_index in range(6):
            success = (index < 5 and path_index == 1) or (5 <= index < 10 and path_index == 2)
            rows.append(_row(f"Q{index}", f"P{path_index}", success))
    assert compute_signal_2(rows).passed


def test_final_decision_requires_all_gates_and_four_signals() -> None:
    signals = [compute_signal_1(_outcomes(2)) for _ in range(4)]
    assert make_decision({"a": True, "b": True, "c": True}, signals)["decision"] == "GO"
    assert make_decision({"a": True, "b": False, "c": True}, signals)["decision"] == "NO-GO"
    assert len(evaluate_qualitative_gates(True, True, False)) == 3
