from __future__ import annotations

from datetime import datetime
from pathlib import Path
from random import Random

import pytest
import yaml

from evidence_routing.annotation import (
    build_blinded_annotation_payload,
    import_reviewed_workbook,
    select_duplicate_questions,
)
from evidence_routing.schemas import (
    ConstructionCategory,
    Domain,
    ExecutionStatus,
    PathId,
    PathRun,
    QueryRecord,
    RankedEvidenceUnit,
    UnitOrigin,
)


def _query(index: int) -> QueryRecord:
    return QueryRecord(
        question_id=f"PHARM-ANNOTATE-{index:03d}",
        domain=Domain.PHARMACEUTICAL,
        language="en",
        query_text=f"What does fictional requirement {index} state?",
        construction_category=ConstructionCategory.DIRECT_CLAUSE,
        source_group_id=f"DOC-{index}",
    )


def _run(query: QueryRecord, path_id: PathId) -> PathRun:
    source_id = f"SOURCE-{query.question_id}"
    return PathRun(
        run_id=f"RUN-{query.question_id}-{path_id.value}",
        question_id=query.question_id,
        path_id=path_id,
        status=ExecutionStatus.COMPLETE,
        ranked_units=[
            RankedEvidenceUnit(
                source_id=source_id,
                document_id=query.source_group_id,
                domain=query.domain,
                source_type="section",
                rank=1,
                origin=UnitOrigin.DIRECT,
                bm25_rank=1,
                bm25_score=1.0,
                provenance={"fixture": "true"},
            )
        ],
        neural_model_calls=int(path_id in {PathId.P1, PathId.P4, PathId.P5}),
        graph_targets_inserted=0,
        context_items_attached=0,
        runtime_ms=1,
    )


def _payload():
    queries = [_query(index) for index in range(1, 21)]
    runs = [_run(query, path_id) for query in queries for path_id in PathId]

    def lookup(run, kind, evidence_id):
        return {
            "heading": f"Heading {evidence_id}",
            "evidence_text": f"Attributable text for {evidence_id}.",
        }

    return queries, runs, lookup


def test_blinding_is_deterministic_and_contains_exactly_120_packages() -> None:
    queries, runs, lookup = _payload()
    first_payload, first_mapping = build_blinded_annotation_payload(
        queries, runs, evidence_text_lookup=lookup, seed=20260723
    )
    second_payload, second_mapping = build_blinded_annotation_payload(
        queries, runs, evidence_text_lookup=lookup, seed=20260723
    )
    assert first_payload == second_payload
    assert first_mapping == second_mapping
    assert len(first_payload["packages"]) == 120
    assert len(first_payload["rows"]) == 20
    assert all("path_id" not in row for row in first_payload["rows"])
    assert {row["path_id"] for row in first_mapping["package_mappings"]} == {
        path_id.value for path_id in PathId
    }


def test_review_import_validates_identity_and_labels() -> None:
    queries, runs, lookup = _payload()
    payload, mapping = build_blinded_annotation_payload(
        queries, runs, evidence_text_lookup=lookup, seed=20260723
    )
    reviewed = [{**row, "label": "REQUIRED"} for row in payload["rows"]]
    annotations = import_reviewed_workbook(
        Path("reviewed.xlsx"),
        payload,
        mapping,
        workbook_reader=lambda _: reviewed,
        annotator_code="ANNOTATOR-A",
        annotated_at=datetime.fromisoformat("2026-07-26T12:00:00+08:00"),
    )
    assert len(annotations) == 120
    assert {row.path_id for row in annotations} == set(PathId)


def test_review_import_rejects_identity_tampering() -> None:
    queries, runs, lookup = _payload()
    payload, mapping = build_blinded_annotation_payload(
        queries, runs, evidence_text_lookup=lookup, seed=20260723
    )
    reviewed = [{**row, "label": "CONTEXT"} for row in payload["rows"]]
    reviewed[0]["question_text"] = "Changed question."
    with pytest.raises(ValueError, match="immutable annotation field changed"):
        import_reviewed_workbook(
            Path("reviewed.xlsx"),
            payload,
            mapping,
            workbook_reader=lambda _: reviewed,
            annotator_code="ANNOTATOR-A",
            annotated_at=datetime.fromisoformat("2026-07-26T12:00:00+08:00"),
        )


def test_duplicate_selection_uses_exact_frozen_strata_and_is_order_invariant() -> None:
    config = yaml.safe_load(Path("configs/pilot-v1.yaml").read_text(encoding="utf-8"))
    quotas = config["annotation"]["duplicate_annotation_quotas"]
    queries = []
    for domain in Domain:
        language = "zh" if domain == Domain.CHEMICAL else "en"
        for category in ConstructionCategory:
            available = config["question_quotas"][domain.value][category.value]
            queries.extend(
                QueryRecord(
                    question_id=(
                        f"{domain.value.upper()}-{category.value.upper()}-{index:02d}"
                    ),
                    domain=domain,
                    language=language,
                    query_text=f"Frozen duplicate-selection question {index}.",
                    construction_category=category,
                    source_group_id=f"GROUP-{domain.value}-{category.value}-{index:02d}",
                )
                for index in range(1, available + 1)
            )

    selected = select_duplicate_questions(
        queries,
        quotas=quotas,
        seed=config["seed"],
    )
    shuffled = queries.copy()
    Random(91).shuffle(shuffled)
    assert selected == select_duplicate_questions(
        shuffled,
        quotas=quotas,
        seed=config["seed"],
    )
    assert len(selected) == config["annotation"]["duplicate_question_count"] == 30

    by_id = {query.question_id: query for query in queries}
    observed = {
        domain.value: {
            category.value: sum(
                by_id[question_id].domain == domain
                and by_id[question_id].construction_category == category
                for question_id in selected
            )
            for category in ConstructionCategory
        }
        for domain in Domain
    }
    assert observed == quotas


def test_duplicate_selection_rejects_unavailable_quota() -> None:
    query = _query(1)
    quotas = {
        domain.value: {category.value: 0 for category in ConstructionCategory}
        for domain in Domain
    }
    quotas["pharmaceutical"]["direct_clause"] = 2
    with pytest.raises(ValueError, match="quota exceeds available questions"):
        select_duplicate_questions([query], quotas=quotas, seed=20260723)
