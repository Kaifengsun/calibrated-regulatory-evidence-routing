"""Source-only fitted cross-domain transfer diagnostics."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import StandardScaler

from evidence_routing.calibration import (
    apply_abstention_policy,
    fit_fold_calibrator,
    select_abstention_threshold,
    select_no_abstention_route,
)
from evidence_routing.metrics import PathOutcome
from evidence_routing.models import fit_logistic_router, fit_xgboost_router
from evidence_routing.policies import derive_path_costs
from evidence_routing.schemas import SplitAssignment


@dataclass(frozen=True)
class TransferDecision:
    question_id: str
    source_domain: str
    target_domain: str
    model_id: str
    selected_path_id: str | None
    abstained: bool
    combined_path_success: bool
    no_abstention_path_id: str
    no_abstention_success: bool
    threshold: float | None
    force_abstain: bool
    source_calibration_hash: str
    selected_path_probability: float | None
    no_abstention_probability: float

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _features(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in {"question_id", "domain"}}


def _fit_model(model_id: str, values: np.ndarray, labels: np.ndarray):
    return (
        fit_logistic_router(values, labels)
        if model_id == "logistic_regression"
        else fit_xgboost_router(values, labels)
    )


def _group_probabilities(rows, probabilities):
    grouped = defaultdict(dict)
    for row, probability in zip(rows, probabilities, strict=True):
        grouped[str(row["question_id"])][str(row["path_id"])] = float(probability)
    return dict(grouped)


def run_cross_domain_transfer(
    feature_rows: Sequence[Mapping[str, Any]],
    outcomes: Sequence[PathOutcome],
    assignments: Sequence[SplitAssignment],
    *,
    source_domain: str,
    target_domain: str,
    model_id: str,
) -> list[TransferDecision]:
    """Fit every learned component on source-domain records only."""
    if source_domain == target_domain:
        raise ValueError("source and target domains must differ")
    if model_id not in {"logistic_regression", "xgboost"}:
        raise ValueError(f"unsupported model: {model_id}")
    outcome_map = {(row.question_id, row.path_id): row.combined_path_success for row in outcomes}
    assignment_by_question = {row.question_id: row for row in assignments}
    source_rows = [row for row in feature_rows if str(row["domain"]) == source_domain]
    target_rows = [row for row in feature_rows if str(row["domain"]) == target_domain]
    if not source_rows or not target_rows:
        raise ValueError("both source and target feature rows are required")
    source_oof_rows = []
    source_oof_probabilities = []
    for fold in range(5):
        train_rows = [
            row
            for row in source_rows
            if assignment_by_question[str(row["question_id"])].fold != fold
        ]
        validation_rows = [
            row
            for row in source_rows
            if assignment_by_question[str(row["question_id"])].fold == fold
        ]
        if not train_rows or not validation_rows:
            raise ValueError("every source-domain fold must contain train and validation rows")
        vectorizer = DictVectorizer(sparse=False)
        train_x = vectorizer.fit_transform([_features(row) for row in train_rows])
        validation_x = vectorizer.transform([_features(row) for row in validation_rows])
        scaler = StandardScaler()
        train_x = scaler.fit_transform(train_x)
        validation_x = scaler.transform(validation_x)
        train_y = np.asarray(
            [outcome_map[(str(row["question_id"]), str(row["path_id"]))] for row in train_rows],
            dtype=int,
        )
        model = _fit_model(model_id, train_x, train_y)
        source_oof_rows.extend(validation_rows)
        source_oof_probabilities.extend(model.predict_probability(validation_x))
    source_oof_y = [
        outcome_map[(str(row["question_id"]), str(row["path_id"]))] for row in source_oof_rows
    ]
    calibrator = fit_fold_calibrator(model_id, source_oof_probabilities, source_oof_y)
    calibrated_source = _group_probabilities(
        source_oof_rows, calibrator.transform(source_oof_probabilities)
    )
    costs = derive_path_costs(outcomes)
    threshold = select_abstention_threshold(calibrated_source, outcome_map, costs)

    vectorizer = DictVectorizer(sparse=False)
    source_x = vectorizer.fit_transform([_features(row) for row in source_rows])
    target_x = vectorizer.transform([_features(row) for row in target_rows])
    scaler = StandardScaler()
    source_x = scaler.fit_transform(source_x)
    target_x = scaler.transform(target_x)
    source_y = np.asarray(
        [outcome_map[(str(row["question_id"]), str(row["path_id"]))] for row in source_rows],
        dtype=int,
    )
    final_model = _fit_model(model_id, source_x, source_y)
    target_probabilities = _group_probabilities(
        target_rows,
        calibrator.transform(final_model.predict_probability(target_x)),
    )
    selective = {
        row.question_id: row
        for row in apply_abstention_policy(target_probabilities, costs, threshold)
    }
    fallback_threshold = threshold.threshold if threshold.threshold is not None else 1.0
    nonselective = {
        row.question_id: row
        for row in select_no_abstention_route(target_probabilities, costs, fallback_threshold)
    }
    source_hash = hashlib.sha256("\n".join(sorted(calibrated_source)).encode()).hexdigest()
    results = []
    for question_id in sorted(target_probabilities):
        selected = selective[question_id]
        fallback = nonselective[question_id]
        results.append(
            TransferDecision(
                question_id=question_id,
                source_domain=source_domain,
                target_domain=target_domain,
                model_id=model_id,
                selected_path_id=selected.selected_path_id,
                abstained=selected.abstained,
                combined_path_success=(
                    False
                    if selected.abstained
                    else outcome_map[(question_id, selected.selected_path_id)]
                ),
                no_abstention_path_id=fallback.selected_path_id,
                no_abstention_success=outcome_map[(question_id, fallback.selected_path_id)],
                threshold=threshold.threshold,
                force_abstain=threshold.force_abstain,
                source_calibration_hash=source_hash,
                selected_path_probability=(
                    None
                    if selected.abstained
                    else target_probabilities[question_id][selected.selected_path_id]
                ),
                no_abstention_probability=target_probabilities[question_id][
                    fallback.selected_path_id
                ],
            )
        )
    return results
