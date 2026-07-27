"""Frozen lightweight probability models for question-path success."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression


@dataclass
class ProbabilityModel:
    """A narrow common interface over the two protocol-approved models."""

    model_id: str
    estimator: object

    def predict_probability(self, features: np.ndarray) -> np.ndarray:
        return self.estimator.predict_proba(features)[:, 1]


def fit_logistic_router(features: np.ndarray, labels: np.ndarray) -> ProbabilityModel:
    """Fit the frozen L2 logistic-regression configuration."""
    estimator = LogisticRegression(
        penalty="l2", C=1.0, solver="lbfgs", max_iter=1000, class_weight=None
    )
    estimator.fit(features, labels)
    return ProbabilityModel("logistic_regression", estimator)


def fit_xgboost_router(
    features: np.ndarray, labels: np.ndarray, seed: int = 20260723
) -> ProbabilityModel:
    """Fit the frozen small XGBoost configuration without parameter search."""
    try:
        from xgboost import XGBClassifier
    except ImportError as error:
        raise RuntimeError("xgboost is required to fit the approved XGBoost router") from error
    estimator = XGBClassifier(
        objective="binary:logistic",
        n_estimators=100,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        n_jobs=1,
        random_state=seed,
        eval_metric="logloss",
    )
    estimator.fit(features, labels)
    return ProbabilityModel("xgboost", estimator)
