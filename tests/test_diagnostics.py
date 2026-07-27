from evidence_routing.diagnostics import summarize_by_construction_category
from evidence_routing.metrics import PathOutcome
from evidence_routing.schemas import QueryRecord


def test_category_diagnostics_are_separate_aggregate_outputs() -> None:
    query = QueryRecord(
        question_id="Q1",
        domain="pharmaceutical",
        language="en",
        query_text="test query",
        construction_category="table_related",
        source_group_id="G1",
    )
    outcomes = [
        PathOutcome(
            "Q1",
            f"P{index}",
            "pharmaceutical",
            index == 2,
            False,
            index == 2,
            0,
            0,
            False,
            int(index in {1, 4, 5}),
            0,
            0,
            1,
        )
        for index in range(6)
    ]
    summary = summarize_by_construction_category([query], outcomes)
    assert summary["feature_use_prohibited"] is True
    assert (
        summary["stage_rescues"]["pharmaceutical"]["table_related"]["context_P2_minus_P0"][
            "rescued_count"
        ]
        == 1
    )
