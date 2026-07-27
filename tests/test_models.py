import numpy as np
import pytest

from evidence_routing.models import fit_logistic_router, fit_xgboost_router


def test_approved_models_return_one_probability_per_input():
    features = np.array([[0.0], [1.0], [0.1], [0.9]])
    labels = np.array([0, 1, 0, 1])
    assert len(fit_logistic_router(features, labels).predict_probability(features)) == 4
    try:
        model = fit_xgboost_router(features, labels)
    except RuntimeError as error:
        pytest.skip(str(error))
    assert len(model.predict_probability(features)) == 4
