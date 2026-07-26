from evidence_routing.schemas import QueryRecord
from evidence_routing.splits import assign_grouped_folds, make_fold_partitions


def _query(question_id: str, group: str) -> QueryRecord:
    return QueryRecord(
        question_id=question_id,
        domain="pharmaceutical",
        language="en",
        query_text="test query",
        construction_category="direct_clause",
        source_group_id=group,
    )


def test_grouped_assignments_are_stable_and_do_not_leak() -> None:
    queries = [_query(f"Q{i}", f"G{i}") for i in range(25)] + [_query("QX", "G0")]
    assigned = assign_grouped_folds(queries)
    assert assigned == assign_grouped_folds(queries)
    partitions = make_fold_partitions(assigned, 0)
    assert "Q0" not in partitions.test_question_ids or "QX" in partitions.test_question_ids
