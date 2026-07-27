from evidence_routing.metrics import PathOutcome
from evidence_routing.schemas import QueryRecord
from evidence_routing.splits import assign_grouped_folds
from evidence_routing.transfer import run_cross_domain_transfer


def test_transfer_fits_source_only_and_predicts_every_target_question() -> None:
    queries = []
    features = []
    outcomes = []
    for domain, prefix in (("chemical", "C"), ("pharmaceutical", "P")):
        for index in range(30):
            query = QueryRecord(
                question_id=f"{prefix}{index}",
                domain=domain,
                language="zh" if domain == "chemical" else "en",
                query_text="测试问题" if domain == "chemical" else "test question",
                construction_category="direct_clause",
                source_group_id=f"{prefix}G{index}",
            )
            queries.append(query)
            for path_index in range(6):
                path_id = f"P{path_index}"
                success = (index + path_index) % 4 == 0
                features.append(
                    {
                        "question_id": query.question_id,
                        "domain": domain,
                        "path_id": path_id,
                        "score": float(index % 3),
                    }
                )
                outcomes.append(
                    PathOutcome(
                        query.question_id,
                        path_id,
                        domain,
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
    results = run_cross_domain_transfer(
        features,
        outcomes,
        assign_grouped_folds(queries),
        source_domain="chemical",
        target_domain="pharmaceutical",
        model_id="logistic_regression",
    )
    assert len(results) == 30
    assert all(row.target_domain == "pharmaceutical" for row in results)
    assert len({row.source_calibration_hash for row in results}) == 1
