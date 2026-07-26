"""Frozen evidence-path outcomes and aggregate Pilot metrics."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from evidence_routing.schemas import EvidenceLabel, EvidenceSpecification, PathRun


@dataclass(frozen=True)
class PathOutcome:
    """One risk-aware outcome for a frozen question-path evidence package."""

    question_id: str
    path_id: str
    domain: str
    evidence_complete: bool
    harmful_expansion: bool
    combined_path_success: bool
    required_found_count: int
    required_total_count: int
    sufficient_found: bool
    neural_model_calls: int
    graph_targets_inserted: int
    context_items_attached: int
    runtime_ms: int

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _final_label_map(
    final_labels: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str, str], str]:
    labels = {}
    allowed = {label.value for label in EvidenceLabel}
    for row in final_labels:
        key = (
            str(row["question_id"]),
            str(row["path_id"]),
            str(row["evidence_id"]),
            str(row["evidence_kind"]),
        )
        if key in labels:
            raise ValueError(f"duplicate final evidence label: {key}")
        label = str(row["label"])
        if label not in allowed:
            raise ValueError(f"invalid final evidence label: {key}/{label}")
        labels[key] = label
    return labels


def compute_path_outcomes(
    specifications: Sequence[EvidenceSpecification],
    runs: Sequence[PathRun],
    final_labels: Sequence[Mapping[str, Any]],
) -> list[PathOutcome]:
    """Evaluate complete evidence, harmful expansion, and combined success."""
    specifications_by_question = {
        row.question_id: row for row in specifications
    }
    if len(specifications_by_question) != len(specifications):
        raise ValueError("evidence specifications must have unique question identities")
    label_by_evidence = _final_label_map(final_labels)
    outcomes = []
    consumed_label_keys = set()

    for run in runs:
        specification = specifications_by_question.get(run.question_id)
        if specification is None:
            raise ValueError(f"path run has no evidence specification: {run.run_id}")
        ranked_source_ids = {unit.source_id for unit in run.ranked_units}
        sidecar_source_ids = {sidecar.source_id for sidecar in run.context_sidecars}
        retrieved_source_ids = ranked_source_ids | sidecar_source_ids
        evidence_keys = [
            (run.question_id, run.path_id.value, unit.source_id, "ranked")
            for unit in run.ranked_units
        ] + [
            (run.question_id, run.path_id.value, sidecar.sidecar_id, "sidecar")
            for sidecar in run.context_sidecars
        ]
        missing_labels = [key for key in evidence_keys if key not in label_by_evidence]
        if missing_labels:
            raise ValueError(f"path evidence lacks final labels: {missing_labels[:3]}")
        consumed_label_keys.update(evidence_keys)
        harmful = any(
            label_by_evidence[key] == EvidenceLabel.HARMFUL.value
            for key in evidence_keys
        )
        required_found = len(set(specification.required_source_ids) & retrieved_source_ids)
        sufficient_found = bool(
            set(specification.sufficient_source_ids) & retrieved_source_ids
        )
        if specification.insufficiency_candidate or run.status.value != "complete":
            complete = False
        elif specification.required_source_ids:
            complete = required_found == len(specification.required_source_ids)
        else:
            complete = sufficient_found
        outcomes.append(
            PathOutcome(
                question_id=run.question_id,
                path_id=run.path_id.value,
                domain=(
                    run.ranked_units[0].domain.value
                    if run.ranked_units
                    else run.context_sidecars[0].domain.value
                ),
                evidence_complete=complete,
                harmful_expansion=harmful,
                combined_path_success=complete and not harmful,
                required_found_count=required_found,
                required_total_count=len(specification.required_source_ids),
                sufficient_found=sufficient_found,
                neural_model_calls=run.neural_model_calls,
                graph_targets_inserted=run.graph_targets_inserted,
                context_items_attached=run.context_items_attached,
                runtime_ms=run.runtime_ms,
            )
        )

    unused = set(label_by_evidence) - consumed_label_keys
    if unused:
        raise ValueError(f"final labels have no matching path evidence: {sorted(unused)[:3]}")
    return sorted(outcomes, key=lambda row: (row.question_id, row.path_id))


def summarize_path_outcomes(
    outcomes: Sequence[PathOutcome],
) -> dict[str, dict[str, dict[str, float | int]]]:
    """Summarize frozen outcomes by path and domain without mixing denominators."""
    grouped: dict[tuple[str, str], list[PathOutcome]] = defaultdict(list)
    for row in outcomes:
        grouped[("all", row.path_id)].append(row)
        grouped[(row.domain, row.path_id)].append(row)

    summary: dict[str, dict[str, dict[str, float | int]]] = defaultdict(dict)
    for (domain, path_id), rows in sorted(grouped.items()):
        count = len(rows)
        summary[domain][path_id] = {
            "question_path_count": count,
            "evidence_complete_count": sum(row.evidence_complete for row in rows),
            "evidence_completeness_rate": sum(row.evidence_complete for row in rows)
            / count,
            "harmful_expansion_count": sum(row.harmful_expansion for row in rows),
            "harmful_expansion_rate": sum(row.harmful_expansion for row in rows)
            / count,
            "combined_path_success_count": sum(
                row.combined_path_success for row in rows
            ),
            "combined_path_success_rate": sum(
                row.combined_path_success for row in rows
            )
            / count,
            "mean_neural_model_calls": sum(row.neural_model_calls for row in rows)
            / count,
            "mean_graph_targets_inserted": sum(
                row.graph_targets_inserted for row in rows
            )
            / count,
            "mean_context_items_attached": sum(
                row.context_items_attached for row in rows
            )
            / count,
            "mean_runtime_ms": sum(row.runtime_ms for row in rows) / count,
        }
    return dict(summary)
