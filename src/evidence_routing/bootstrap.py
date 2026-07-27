"""Frozen question-level paired bootstrap uncertainty estimates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

import numpy as np
from scipy.stats import binomtest


@dataclass(frozen=True)
class BootstrapDifference:
    observed_difference: float
    confidence_level: float
    lower: float
    upper: float
    iterations: int
    seed: int

    def model_dump(self) -> dict[str, float | int]:
        return asdict(self)


@dataclass(frozen=True)
class PairedBinaryComparison:
    difference: BootstrapDifference
    first_only_successes: int
    second_only_successes: int
    mcnemar_exact_p_value: float

    def model_dump(self) -> dict[str, object]:
        return {
            "difference": self.difference.model_dump(),
            "first_only_successes": self.first_only_successes,
            "second_only_successes": self.second_only_successes,
            "mcnemar_exact_p_value": self.mcnemar_exact_p_value,
        }


def paired_bootstrap(
    first: Sequence[float | int | bool],
    second: Sequence[float | int | bool],
    *,
    iterations: int = 10_000,
    seed: int = 20260723,
    confidence_level: float = 0.95,
) -> BootstrapDifference:
    """Estimate the paired mean difference ``first - second`` by question."""
    first_values = np.asarray(first, dtype=float)
    second_values = np.asarray(second, dtype=float)
    if first_values.ndim != 1 or second_values.ndim != 1:
        raise ValueError("paired bootstrap inputs must be one-dimensional")
    if not len(first_values) or len(first_values) != len(second_values):
        raise ValueError("paired bootstrap inputs must be non-empty and aligned")
    if iterations != 10_000 or seed != 20260723:
        raise ValueError("the frozen Pilot requires 10,000 iterations and seed 20260723")
    if confidence_level != 0.95:
        raise ValueError("the frozen Pilot uses a 95% interval")
    differences = first_values - second_values
    generator = np.random.default_rng(seed)
    samples = generator.integers(0, len(differences), size=(iterations, len(differences)))
    means = differences[samples].mean(axis=1)
    alpha = (1 - confidence_level) / 2
    lower, upper = np.quantile(means, [alpha, 1 - alpha])
    return BootstrapDifference(
        observed_difference=float(differences.mean()),
        confidence_level=confidence_level,
        lower=float(lower),
        upper=float(upper),
        iterations=iterations,
        seed=seed,
    )


def paired_binary_comparison(
    first: Sequence[bool | int], second: Sequence[bool | int]
) -> PairedBinaryComparison:
    """Combine a paired bootstrap interval with an exact McNemar test."""
    if not first or len(first) != len(second):
        raise ValueError("binary comparison inputs must be non-empty and aligned")
    if any(value not in {0, 1, False, True} for value in [*first, *second]):
        raise ValueError("binary comparison inputs must contain only zero or one")
    first_only = sum(bool(a) and not bool(b) for a, b in zip(first, second, strict=True))
    second_only = sum(bool(b) and not bool(a) for a, b in zip(first, second, strict=True))
    discordant = first_only + second_only
    p_value = (
        float(binomtest(min(first_only, second_only), discordant, 0.5).pvalue)
        if discordant
        else 1.0
    )
    return PairedBinaryComparison(
        difference=paired_bootstrap(first, second),
        first_only_successes=first_only,
        second_only_successes=second_only,
        mcnemar_exact_p_value=p_value,
    )
