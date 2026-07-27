from evidence_routing.evaluation import run_pooled_oof
from evidence_routing.metrics import PathOutcome
from evidence_routing.schemas import QueryRecord
from evidence_routing.splits import assign_grouped_folds


def test_pooled_oof_predicts_each_question_once() -> None:
    queries = [
        QueryRecord(
            question_id=f"Q{i}",
            domain="pharmaceutical",
            language="en",
            query_text="test query",
            construction_category="direct_clause",
            source_group_id=f"G{i}",
        )
        for i in range(40)
    ]
    features = []
    outcomes = []
    for index, query in enumerate(queries):
        for path_index in range(6):
            path_id = f"P{path_index}"
            success = (index + path_index) % 3 == 0
            features.append(
                {
                    "question_id": query.question_id,
                    "domain": "pharmaceutical",
                    "path_id": path_id,
                    "value": float(index % 5),
                }
            )
            outcomes.append(
                PathOutcome(
                    query.question_id,
                    path_id,
                    "pharmaceutical",
                    success,
                    False,
                    success,
                    0,
                    0,
                    False,
                    int(path_id in {"P1", "P4", "P5"}),
                    0,
                    0,
                    1,
                )
            )
    decisions = run_pooled_oof(
        features, outcomes, assign_grouped_folds(queries), "logistic_regression"
    )
    assert len(decisions) == 40
    assert len({row.question_id for row in decisions}) == 40
    assert all(len(row.calibration_partition_hash) == 64 for row in decisions)
