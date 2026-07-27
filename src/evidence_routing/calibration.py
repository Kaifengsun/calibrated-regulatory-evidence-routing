"""Calibration-only threshold selection and evidence-sufficiency abstention."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression

from evidence_routing.policies import PathCost, RouteDecision


@dataclass(frozen=True)
class FoldCalibrator:
    model_id: str
    method: str
    estimator: LogisticRegression | None = None
    constant_value: float | None = None

    def transform(self, probabilities: Sequence[float]) -> np.ndarray:
        values = np.asarray(probabilities, dtype=float)
        if self.method == "identity":
            return values
        if self.method == "constant":
            return np.full(len(values), self.constant_value)
        logits = np.log(np.clip(values, 1e-6, 1 - 1e-6) / np.clip(1 - values, 1e-6, 1))
        return self.estimator.predict_proba(logits.reshape(-1, 1))[:, 1]


@dataclass(frozen=True)
class AbstentionThreshold:
    threshold: float | None
    force_abstain: bool
    accepted_count: int
    accepted_failure_rate: float | None


def fit_fold_calibrator(
    model_id: str, probabilities: Sequence[float], labels: Sequence[int]
) -> FoldCalibrator:
    """Use native LR probabilities; Platt-scale XGBoost only on calibration data."""
    if model_id == "logistic_regression":
        return FoldCalibrator(model_id, "identity")
    if model_id != "xgboost":
        raise ValueError(f"unsupported model for calibration: {model_id}")
    y = np.asarray(labels, dtype=int)
    if len(y) != len(probabilities) or not len(y):
        raise ValueError("calibration probabilities and labels must be non-empty and aligned")
    if len(np.unique(y)) < 2:
        return FoldCalibrator(model_id, "constant", constant_value=float(y[0]))
    values = np.asarray(probabilities, dtype=float)
    logits = np.log(np.clip(values, 1e-6, 1 - 1e-6) / np.clip(1 - values, 1e-6, 1))
    estimator = LogisticRegression(solver="lbfgs", max_iter=1000).fit(logits.reshape(-1, 1), y)
    return FoldCalibrator(model_id, "platt", estimator)


def _select(
    probabilities: Mapping[str, Mapping[str, float]],
    costs: Mapping[str, PathCost],
    threshold: float | None,
) -> list[RouteDecision]:
    decisions = []
    for question_id, per_path in sorted(probabilities.items()):
        eligible = [
            path for path, value in per_path.items() if threshold is not None and value >= threshold
        ]
        if not eligible:
            decisions.append(RouteDecision(question_id, "learned", None, True))
        else:
            path_id = min(eligible, key=lambda path: costs[path].tuple)
            decisions.append(RouteDecision(question_id, "learned", path_id, False))
    return decisions


def select_abstention_threshold(
    calibration_probabilities: Mapping[str, Mapping[str, float]],
    outcomes: Mapping[tuple[str, str], bool],
    costs: Mapping[str, PathCost],
) -> AbstentionThreshold:
    """Choose the smallest valid calibration-only threshold or force abstention."""
    candidates = sorted(
        {value for paths in calibration_probabilities.values() for value in paths.values()}
    )
    valid = []
    for threshold in candidates:
        decisions = _select(calibration_probabilities, costs, threshold)
        accepted = [row for row in decisions if not row.abstained]
        if len(accepted) < 10:
            continue
        failure_rate = 1 - sum(
            outcomes[(row.question_id, row.selected_path_id)] for row in accepted
        ) / len(accepted)
        if failure_rate <= 0.10:
            valid.append((threshold, len(accepted), failure_rate))
    if not valid:
        return AbstentionThreshold(None, True, 0, None)
    threshold, count, failure_rate = valid[0]
    return AbstentionThreshold(threshold, False, count, failure_rate)


def apply_abstention_policy(
    probabilities: Mapping[str, Mapping[str, float]],
    costs: Mapping[str, PathCost],
    selection: AbstentionThreshold,
) -> list[RouteDecision]:
    """Apply a calibration-selected threshold unchanged to an outer test partition."""
    return _select(probabilities, costs, None if selection.force_abstain else selection.threshold)


def select_no_abstention_route(
    probabilities: Mapping[str, Mapping[str, float]],
    costs: Mapping[str, PathCost],
    threshold: float,
) -> list[RouteDecision]:
    """Use threshold-eligible cheapest path, then highest-probability fallback."""
    decisions = _select(probabilities, costs, threshold)
    resolved = []
    for decision in decisions:
        if not decision.abstained:
            resolved.append(
                RouteDecision(
                    decision.question_id, "learned_no_abstention", decision.selected_path_id, False
                )
            )
            continue
        per_path = probabilities[decision.question_id]
        maximum = max(per_path.values())
        eligible = [path for path, value in per_path.items() if value == maximum]
        resolved.append(
            RouteDecision(
                decision.question_id,
                "learned_no_abstention",
                min(eligible, key=lambda path: costs[path].tuple),
                False,
            )
        )
    return resolved
