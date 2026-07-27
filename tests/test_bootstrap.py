import pytest

from evidence_routing.bootstrap import paired_binary_comparison, paired_bootstrap


def test_paired_bootstrap_is_reproducible_and_paired() -> None:
    first = [1, 1, 0, 1, 0]
    second = [0, 1, 0, 0, 1]
    result = paired_bootstrap(first, second)
    assert result == paired_bootstrap(first, second)
    assert result.observed_difference == pytest.approx(0.2)
    assert result.lower <= result.observed_difference <= result.upper


def test_paired_bootstrap_rejects_nonfrozen_settings() -> None:
    with pytest.raises(ValueError, match="10,000"):
        paired_bootstrap([1], [0], iterations=9999)


def test_binary_comparison_reports_discordance_and_exact_p_value() -> None:
    result = paired_binary_comparison([1, 1, 0, 1], [0, 1, 0, 0])
    assert result.first_only_successes == 2
    assert result.second_only_successes == 0
    assert result.mcnemar_exact_p_value == 0.5
