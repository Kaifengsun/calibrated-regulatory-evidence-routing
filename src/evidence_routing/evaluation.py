"""Leakage-safe pooled out-of-fold evaluation for the frozen Pilot."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
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
from evidence_routing.splits import make_fold_partitions


@dataclass(frozen=True)
class OOFDecision:
    question_id: str
    fold: int
    model_id: str
    selected_path_id: str | None
    abstained: bool
    combined_path_success: bool
    no_abstention_path_id: str
    no_abstention_success: bool
    threshold: float | None
    force_abstain: bool
    calibration_partition_hash: str
    selected_path_probability: float | None
    no_abstention_probability: float

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _model_features(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "question_id"}


def _group_probabilities(
    rows: Sequence[Mapping[str, Any]], probabilities: Sequence[float]
) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, float]] = defaultdict(dict)
    for row, probability in zip(rows, probabilities, strict=True):
        question_id = str(row["question_id"])
        path_id = str(row["path_id"])
        if path_id in grouped[question_id]:
            raise ValueError(f"duplicate question-path probability: {question_id}/{path_id}")
        grouped[question_id][path_id] = float(probability)
    return dict(grouped)


def run_pooled_oof(
    feature_rows: Sequence[Mapping[str, Any]],
    outcomes: Sequence[PathOutcome],
    assignments: Sequence[SplitAssignment],
    model_id: str,
) -> list[OOFDecision]:
    """Fit, calibrate, and test five grouped folds without test-fold reuse."""
    if model_id not in {"logistic_regression", "xgboost"}:
        raise ValueError(f"unsupported router: {model_id}")
    outcome_map = {(row.question_id, row.path_id): row.combined_path_success for row in outcomes}
    if len(outcome_map) != len(outcomes):
        raise ValueError("path outcomes must have unique question-path identities")
    counts = Counter(str(row["question_id"]) for row in feature_rows)
    if set(counts.values()) != {6}:
        raise ValueError("feature rows must contain exactly six paths per question")
    by_question: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in feature_rows:
        by_question[str(row["question_id"])].append(row)
    costs = derive_path_costs(outcomes)
    decisions: list[OOFDecision] = []

    for fold in range(5):
        partitions = make_fold_partitions(assignments, fold)
        train_rows = [row for qid in partitions.train_question_ids for row in by_question[qid]]
        calibration_rows = [
            row for qid in partitions.calibration_question_ids for row in by_question[qid]
        ]
        test_rows = [row for qid in partitions.test_question_ids for row in by_question[qid]]
        vectorizer = DictVectorizer(sparse=False)
        train_x = vectorizer.fit_transform([_model_features(row) for row in train_rows])
        calibration_x = vectorizer.transform([_model_features(row) for row in calibration_rows])
        test_x = vectorizer.transform([_model_features(row) for row in test_rows])
        scaler = StandardScaler()
        train_x = scaler.fit_transform(train_x)
        calibration_x = scaler.transform(calibration_x)
        test_x = scaler.transform(test_x)
        train_y = np.asarray(
            [outcome_map[(str(row["question_id"]), str(row["path_id"]))] for row in train_rows],
            dtype=int,
        )
        calibration_y = np.asarray(
            [
                outcome_map[(str(row["question_id"]), str(row["path_id"]))]
                for row in calibration_rows
            ],
            dtype=int,
        )
        model = (
            fit_logistic_router(train_x, train_y)
            if model_id == "logistic_regression"
            else fit_xgboost_router(train_x, train_y)
        )
        calibrator = fit_fold_calibrator(
            model_id, model.predict_probability(calibration_x), calibration_y
        )
        calibration_probabilities = _group_probabilities(
            calibration_rows,
            calibrator.transform(model.predict_probability(calibration_x)),
        )
        threshold = select_abstention_threshold(calibration_probabilities, outcome_map, costs)
        test_probabilities = _group_probabilities(
            test_rows, calibrator.transform(model.predict_probability(test_x))
        )
        selective = {
            row.question_id: row
            for row in apply_abstention_policy(test_probabilities, costs, threshold)
        }
        fallback_threshold = threshold.threshold if threshold.threshold is not None else 1.0
        nonselective = {
            row.question_id: row
            for row in select_no_abstention_route(test_probabilities, costs, fallback_threshold)
        }
        partition_hash = hashlib.sha256(
            "\n".join(partitions.calibration_question_ids).encode()
        ).hexdigest()
        for question_id in partitions.test_question_ids:
            selected = selective[question_id]
            no_abstention = nonselective[question_id]
            decisions.append(
                OOFDecision(
                    question_id=question_id,
                    fold=fold,
                    model_id=model_id,
                    selected_path_id=selected.selected_path_id,
                    abstained=selected.abstained,
                    combined_path_success=(
                        False
                        if selected.abstained
                        else outcome_map[(question_id, selected.selected_path_id)]
                    ),
                    no_abstention_path_id=no_abstention.selected_path_id,
                    no_abstention_success=outcome_map[
                        (question_id, no_abstention.selected_path_id)
                    ],
                    threshold=threshold.threshold,
                    force_abstain=threshold.force_abstain,
                    calibration_partition_hash=partition_hash,
                    selected_path_probability=(
                        None
                        if selected.abstained
                        else test_probabilities[question_id][selected.selected_path_id]
                    ),
                    no_abstention_probability=test_probabilities[question_id][
                        no_abstention.selected_path_id
                    ],
                )
            )
    if len(decisions) != len(assignments):
        raise AssertionError("pooled OOF evaluation did not predict every question once")
    return sorted(decisions, key=lambda row: row.question_id)
