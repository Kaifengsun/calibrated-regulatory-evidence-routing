import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evidence_routing.schemas import (
    SCHEMA_MODELS,
    EvidenceAnnotation,
    PathRun,
    QueryRecord,
    QuestionAnnotationBundle,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "data" / "templates"


def test_regulatory_identifiers_allow_standard_spacing_and_slashes() -> None:
    payload = json.loads((TEMPLATES / "query-record.example.json").read_text(encoding="utf-8"))
    payload["source_group_id"] = "GB/T 12345-2026"
    payload["authoring_source_ids"] = ["AQ 1011-2005:normal:5.2"]
    record = QueryRecord.model_validate(payload)
    assert record.source_group_id == "GB/T 12345-2026"
    assert record.authoring_source_ids == ["AQ 1011-2005:normal:5.2"]


def test_regulatory_identifiers_reject_embedded_control_characters() -> None:
    payload = json.loads((TEMPLATES / "query-record.example.json").read_text(encoding="utf-8"))
    payload["source_group_id"] = "GB/T 12345\ninvalid"
    with pytest.raises(ValidationError):
        QueryRecord.model_validate(payload)


SCHEMAS = ROOT / "data" / "schemas"


@pytest.mark.parametrize("model_name", sorted(SCHEMA_MODELS))
def test_safe_template_validates(model_name: str) -> None:
    payload = json.loads((TEMPLATES / f"{model_name}.example.json").read_text(encoding="utf-8"))
    SCHEMA_MODELS[model_name].model_validate(payload)


@pytest.mark.parametrize("model_name", sorted(SCHEMA_MODELS))
def test_committed_json_schema_matches_model(model_name: str) -> None:
    committed = json.loads((SCHEMAS / f"{model_name}-v1.schema.json").read_text(encoding="utf-8"))
    assert committed == SCHEMA_MODELS[model_name].model_json_schema()


def test_unknown_schema_version_is_rejected() -> None:
    payload = json.loads((TEMPLATES / "query-record.example.json").read_text(encoding="utf-8"))
    payload["schema_version"] = "2.0"
    with pytest.raises(ValidationError, match="schema_version"):
        QueryRecord.model_validate(payload)


def test_empty_identifier_is_rejected() -> None:
    payload = json.loads((TEMPLATES / "query-record.example.json").read_text(encoding="utf-8"))
    payload["authoring_source_ids"] = [""]
    with pytest.raises(ValidationError, match="authoring_source_ids"):
        QueryRecord.model_validate(payload)


def test_missing_provenance_is_rejected() -> None:
    payload = json.loads((TEMPLATES / "path-run.example.json").read_text(encoding="utf-8"))
    payload["ranked_units"][0]["provenance"] = {}
    with pytest.raises(ValidationError, match="provenance"):
        PathRun.model_validate(payload)


def test_illegal_path_id_is_rejected() -> None:
    payload = json.loads((TEMPLATES / "path-run.example.json").read_text(encoding="utf-8"))
    payload["path_id"] = "P6"
    with pytest.raises(ValidationError, match="path_id"):
        PathRun.model_validate(payload)


def test_harmful_annotation_requires_reason() -> None:
    payload = json.loads(
        (TEMPLATES / "evidence-annotation.example.json").read_text(encoding="utf-8")
    )
    payload["label"] = "HARMFUL"
    with pytest.raises(ValidationError, match="harmful_reason_code"):
        EvidenceAnnotation.model_validate(payload)


def test_corpus_insufficiency_requires_manual_negative_search() -> None:
    payload = json.loads(
        (TEMPLATES / "question-annotation-bundle.example.json").read_text(encoding="utf-8")
    )
    payload["corpus_assessment"] = "insufficient"
    with pytest.raises(ValidationError, match="manual check"):
        QuestionAnnotationBundle.model_validate(payload)


def test_six_failed_paths_cannot_encode_corpus_insufficiency() -> None:
    payload = json.loads(
        (TEMPLATES / "question-annotation-bundle.example.json").read_text(encoding="utf-8")
    )
    payload["evidence_annotations"] = []
    payload["corpus_assessment"] = "unchecked"
    record = QuestionAnnotationBundle.model_validate(payload)
    assert record.corpus_assessment.value == "unchecked"
