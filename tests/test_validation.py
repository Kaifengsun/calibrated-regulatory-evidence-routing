import json
from pathlib import Path

import pytest

from evidence_routing.schemas import (
    EvidenceSpecification,
    ExperimentManifest,
    PathRun,
    QueryRecord,
)
from evidence_routing.validation import (
    DatasetValidationError,
    validate_dataset,
    validate_manifest,
    validate_path_run,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "data" / "templates"


def _load(name: str) -> dict:
    return json.loads((TEMPLATES / name).read_text(encoding="utf-8"))


def test_duplicate_ranked_evidence_is_rejected_with_stable_code() -> None:
    payload = _load("path-run.example.json")
    duplicate = dict(payload["ranked_units"][0])
    duplicate["rank"] = 2
    payload["ranked_units"].append(duplicate)
    run = PathRun.model_validate(payload)
    with pytest.raises(DatasetValidationError) as captured:
        validate_path_run(run)
    assert [issue.code for issue in captured.value.issues] == ["E_EVIDENCE_ID_DUPLICATE"]


def test_nonconsecutive_rank_is_rejected_with_stable_code() -> None:
    payload = _load("path-run.example.json")
    payload["ranked_units"][0]["rank"] = 2
    run = PathRun.model_validate(payload)
    with pytest.raises(DatasetValidationError) as captured:
        validate_path_run(run)
    assert [issue.code for issue in captured.value.issues] == ["E_RANK_SEQUENCE"]


def test_query_specification_identity_mismatch_is_rejected() -> None:
    query = QueryRecord.model_validate(_load("query-record.example.json"))
    payload = _load("evidence-specification.example.json")
    payload["question_id"] = "CHEM-PILOT-999"
    specification = EvidenceSpecification.model_validate(payload)
    with pytest.raises(DatasetValidationError) as captured:
        validate_dataset([query], [specification], require_frozen_counts=False)
    assert [issue.code for issue in captured.value.issues] == ["E_QUERY_SPEC_MISMATCH"]


def test_manifest_requires_input_and_configuration_hashes() -> None:
    payload = _load("experiment-manifest.example.json")
    payload["input_hashes"] = {}
    manifest = ExperimentManifest.model_validate(payload)
    with pytest.raises(DatasetValidationError) as captured:
        validate_manifest(manifest)
    assert [issue.code for issue in captured.value.issues] == ["E_INPUT_HASH_MISSING"]
