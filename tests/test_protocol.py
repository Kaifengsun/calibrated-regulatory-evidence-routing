import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

FROZEN_HASHES = {
    "pilot-v1.yaml": "bd405ca9561ea407f833e0ea48842a44fbedfa6160f00a747499d6b3450a0b40",
    "cues-v1.yaml": "fa811d1fb4843bd950b2a9ddd5955cd25df5ae13ac82819b79a8d0b9897a995a",
    "reranker-v1.yaml": "f8352e9e04ea9d2a91cb6e5d90f552321d5a5add67a36e33db7db06c9cffadd6",
}


def test_frozen_configuration_hashes() -> None:
    for name, expected in FROZEN_HASHES.items():
        actual = hashlib.sha256((ROOT / "configs" / name).read_bytes()).hexdigest()
        assert actual == expected, f"{name} changed without a protocol version update"


def test_frozen_pilot_counts_and_paths() -> None:
    protocol = yaml.safe_load((ROOT / "configs" / "pilot-v1.yaml").read_text("utf-8"))
    assert protocol["total_question_count"] == 120
    assert protocol["domains"]["chemical"]["question_count"] == 60
    assert protocol["domains"]["pharmaceutical"]["question_count"] == 60
    assert protocol["questions_per_domain_category"] == 12
    assert set(protocol["paths"]) == {f"P{index}" for index in range(6)}
    assert protocol["annotation"]["duplicate_question_count"] == 30


def test_test_fold_threshold_search_is_forbidden() -> None:
    protocol = yaml.safe_load((ROOT / "configs" / "pilot-v1.yaml").read_text("utf-8"))
    assert protocol["calibration"]["test_threshold_search_allowed"] is False
    assert protocol["calibration"]["no_valid_threshold_action"] == "force_abstain"
