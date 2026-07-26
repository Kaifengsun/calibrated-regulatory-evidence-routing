from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from evidence_routing.authoring import (
    AuthoringRecord,
    PriorQuestionCheck,
    ReviewDecision,
)
from evidence_routing.review import (
    build_prefreeze_review_payload,
    export_prefreeze_review,
    import_prefreeze_review,
)
from evidence_routing.schemas import (
    ConstructionCategory,
    Domain,
    EvidenceSpecification,
    QueryRecord,
)


def _records():
    query = QueryRecord(
        question_id="Q-001",
        domain=Domain.PHARMACEUTICAL,
        language="en",
        query_text="What control is required?",
        construction_category=ConstructionCategory.DIRECT_CLAUSE,
        source_group_id="DOC-1",
        authoring_source_ids=["DOC-1:C1"],
        counter_cue_tags=[],
    )
    specification = EvidenceSpecification(
        question_id="Q-001",
        specification_id="SPEC-001",
        required_source_ids=[],
        sufficient_source_ids=["DOC-1:C1"],
        evidence_scope_note="The direct clause supplies the complete answer.",
    )
    authoring = AuthoringRecord(
        authoring_id="AUTH-001",
        question_id="Q-001",
        specification_id="SPEC-001",
        domain=Domain.PHARMACEUTICAL,
        construction_category=ConstructionCategory.DIRECT_CLAUSE,
        review_decision=ReviewDecision.READY_FOR_REVIEW,
        construction_rationale="A single attributable clause supplies the answer.",
        prior_question_check=PriorQuestionCheck.CLEAR,
        source_resolution_checked=True,
    )
    return [query], [specification], [authoring]


def test_review_payload_is_deterministic_and_contains_identity_hash():
    queries, specifications, authoring = _records()
    first = build_prefreeze_review_payload(queries, specifications, authoring)
    second = build_prefreeze_review_payload(queries, specifications, authoring)
    assert first == second
    assert len(first["rows"][0]["identity_sha256"]) == 64


def test_export_uses_injected_workbook_writer(tmp_path: Path):
    queries, specifications, authoring = _records()
    captured = {}

    def writer(path, payload):
        captured["path"] = path
        captured["payload"] = payload

    destination = tmp_path / "review.xlsx"
    payload = export_prefreeze_review(
        destination,
        queries,
        specifications,
        authoring,
        workbook_writer=writer,
    )
    assert captured == {"path": destination, "payload": payload}


def test_import_accepts_complete_review():
    queries, specifications, authoring = _records()
    baseline = build_prefreeze_review_payload(
        queries,
        specifications,
        authoring,
    )
    reviewed = {**baseline["rows"][0]}
    reviewed.update(
        {
            "review_decision": "accept",
            "evidence_complete": "yes",
            "category_correct": "yes",
            "wording_natural": "yes",
            "prior_overlap_clear": "yes",
        }
    )
    result = import_prefreeze_review(
        Path("review.xlsx"),
        baseline,
        authoring,
        workbook_reader=lambda _: [reviewed],
        reviewer_id="reviewer-a",
        reviewed_at=datetime(2026, 7, 26, tzinfo=UTC),
    )
    assert result[0].review_decision == ReviewDecision.ACCEPT
    assert result[0].reviewed_by == "reviewer-a"


def test_import_rejects_immutable_cell_change():
    queries, specifications, authoring = _records()
    baseline = build_prefreeze_review_payload(
        queries,
        specifications,
        authoring,
    )
    changed = {**baseline["rows"][0], "query_text": "Changed question"}
    changed["review_decision"] = "reject_and_replace"
    with pytest.raises(ValueError, match="immutable review field changed"):
        import_prefreeze_review(
            Path("review.xlsx"),
            baseline,
            authoring,
            workbook_reader=lambda _: [changed],
            reviewer_id="reviewer-a",
            reviewed_at=datetime(2026, 7, 26, tzinfo=UTC),
        )


def test_import_rejects_accept_without_full_checklist():
    queries, specifications, authoring = _records()
    baseline = build_prefreeze_review_payload(
        queries,
        specifications,
        authoring,
    )
    reviewed = {**baseline["rows"][0], "review_decision": "accept"}
    with pytest.raises(ValueError, match="incomplete checklist"):
        import_prefreeze_review(
            Path("review.xlsx"),
            baseline,
            authoring,
            workbook_reader=lambda _: [reviewed],
            reviewer_id="reviewer-a",
            reviewed_at=datetime(2026, 7, 26, tzinfo=UTC),
        )
