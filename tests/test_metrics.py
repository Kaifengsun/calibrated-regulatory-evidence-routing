from __future__ import annotations

from evidence_routing.metrics import (
    brier_score,
    compute_path_outcomes,
    frozen_bin_ece,
    selective_metrics,
    summarize_path_outcomes,
)
from evidence_routing.schemas import (
    Domain,
    EvidenceSpecification,
    ExecutionStatus,
    PathId,
    PathRun,
    RankedEvidenceUnit,
    UnitOrigin,
)


def _run(source_ids: list[str]) -> PathRun:
    return PathRun(
        run_id="RUN-001-P0",
        question_id="QUESTION-001",
        path_id=PathId.P0,
        status=ExecutionStatus.COMPLETE,
        ranked_units=[
            RankedEvidenceUnit(
                source_id=source_id,
                document_id="DOC-001",
                domain=Domain.CHEMICAL,
                source_type="section",
                rank=index,
                origin=UnitOrigin.DIRECT,
                bm25_rank=index,
                bm25_score=float(11 - index),
                provenance={"fixture": "true"},
            )
            for index, source_id in enumerate(source_ids, 1)
        ],
        neural_model_calls=0,
        graph_targets_inserted=0,
        context_items_attached=0,
        runtime_ms=10,
    )


def _labels(run: PathRun, labels: list[str]) -> list[dict[str, str]]:
    return [
        {
            "question_id": run.question_id,
            "path_id": run.path_id.value,
            "evidence_id": unit.source_id,
            "evidence_kind": "ranked",
            "label": label,
        }
        for unit, label in zip(run.ranked_units, labels, strict=True)
    ]


def test_required_evidence_and_harm_are_reported_separately() -> None:
    run = _run(["REQ-1", "REQ-2", "NOISE"])
    specification = EvidenceSpecification(
        question_id=run.question_id,
        specification_id="SPEC-001",
        required_source_ids=["REQ-1", "REQ-2"],
        evidence_scope_note="Both clauses are necessary.",
    )
    outcome = compute_path_outcomes(
        [specification],
        [run],
        _labels(run, ["REQUIRED", "REQUIRED", "HARMFUL"]),
    )[0]
    assert outcome.evidence_complete is True
    assert outcome.harmful_expansion is True
    assert outcome.combined_path_success is False
    assert outcome.required_found_count == 2


def test_sufficient_evidence_and_insufficiency_candidate() -> None:
    run = _run(["SUFF-1"])
    sufficient = EvidenceSpecification(
        question_id=run.question_id,
        specification_id="SPEC-001",
        sufficient_source_ids=["SUFF-1"],
        evidence_scope_note="One clause is sufficient.",
    )
    outcome = compute_path_outcomes([sufficient], [run], _labels(run, ["SUFFICIENT"]))[0]
    assert outcome.combined_path_success is True

    insufficient = sufficient.model_copy(
        update={
            "required_source_ids": [],
            "sufficient_source_ids": [],
            "insufficiency_candidate": True,
        }
    )
    outcome = compute_path_outcomes([insufficient], [run], _labels(run, ["IRRELEVANT"]))[0]
    assert outcome.evidence_complete is False
    assert outcome.combined_path_success is False


def test_summary_reports_rates_and_costs_by_path_and_domain() -> None:
    run = _run(["SUFF-1"])
    specification = EvidenceSpecification(
        question_id=run.question_id,
        specification_id="SPEC-001",
        sufficient_source_ids=["SUFF-1"],
        evidence_scope_note="One clause is sufficient.",
    )
    outcomes = compute_path_outcomes([specification], [run], _labels(run, ["SUFFICIENT"]))
    summary = summarize_path_outcomes(outcomes)
    assert summary["all"]["P0"]["combined_path_success_rate"] == 1.0
    assert summary["chemical"]["P0"]["mean_runtime_ms"] == 10.0


def test_probability_and_selective_metrics_have_explicit_denominators() -> None:
    assert brier_score([0.0, 1.0], [0, 1]) == 0.0
    assert frozen_bin_ece([0.0, 1.0], [0, 1]) == 0.0
    result = selective_metrics([True, False], [True, False])
    assert result["question_count"] == 2
    assert result["accepted_count"] == 1
    assert result["coverage"] == 0.5
