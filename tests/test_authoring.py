import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evidence_routing.authoring import (
    AUTHORING_SCHEMA_MODELS,
    AuthoringRecord,
    ManualSearchRecord,
    ReviewDecision,
    validate_review_transition,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "data" / "templates"
SCHEMAS = ROOT / "data" / "schemas"


@pytest.mark.parametrize("model_name", sorted(AUTHORING_SCHEMA_MODELS))
def test_safe_authoring_template_validates(model_name: str) -> None:
    payload = json.loads(
        (TEMPLATES / f"{model_name}.example.json").read_text(encoding="utf-8")
    )
    AUTHORING_SCHEMA_MODELS[model_name].model_validate(payload)


@pytest.mark.parametrize("model_name", sorted(AUTHORING_SCHEMA_MODELS))
def test_committed_authoring_schema_matches_model(model_name: str) -> None:
    committed = json.loads(
        (SCHEMAS / f"{model_name}-v1.schema.json").read_text(encoding="utf-8")
    )
    assert committed == AUTHORING_SCHEMA_MODELS[model_name].model_json_schema()


def test_insufficient_acceptance_requires_manual_search_record() -> None:
    payload = json.loads(
        (TEMPLATES / "authoring-record.example.json").read_text(encoding="utf-8")
    )
    payload["construction_category"] = "evidence_insufficient"
    with pytest.raises(ValidationError, match="manual search record"):
        AuthoringRecord.model_validate(payload)


def test_acceptance_requires_source_and_prior_question_checks() -> None:
    payload = json.loads(
        (TEMPLATES / "authoring-record.example.json").read_text(encoding="utf-8")
    )
    payload["source_resolution_checked"] = False
    payload["prior_question_check"] = "review_required"
    with pytest.raises(ValidationError, match="resolved source"):
        AuthoringRecord.model_validate(payload)


def test_manual_search_conclusion_must_match_result() -> None:
    payload = json.loads(
        (TEMPLATES / "manual-search-record.example.json").read_text(encoding="utf-8")
    )
    payload["evidence_found"] = True
    with pytest.raises(ValidationError, match="conclusion"):
        ManualSearchRecord.model_validate(payload)


def test_authoring_records_reject_source_text_and_local_paths() -> None:
    payload = json.loads(
        (TEMPLATES / "authoring-record.example.json").read_text(encoding="utf-8")
    )
    payload["source_excerpt"] = "restricted source text"
    payload["local_path"] = "machine-local-location"
    with pytest.raises(ValidationError, match="Extra inputs"):
        AuthoringRecord.model_validate(payload)


@pytest.mark.parametrize(
    ("previous", "new"),
    [
        (ReviewDecision.DRAFT, ReviewDecision.READY_FOR_REVIEW),
        (ReviewDecision.READY_FOR_REVIEW, ReviewDecision.ACCEPT),
        (ReviewDecision.READY_FOR_REVIEW, ReviewDecision.REVISE_AND_REVIEW),
        (ReviewDecision.REVISE_AND_REVIEW, ReviewDecision.READY_FOR_REVIEW),
    ],
)
def test_legal_review_transitions(
    previous: ReviewDecision,
    new: ReviewDecision,
) -> None:
    validate_review_transition(previous, new)


@pytest.mark.parametrize(
    ("previous", "new"),
    [
        (ReviewDecision.DRAFT, ReviewDecision.ACCEPT),
        (ReviewDecision.ACCEPT, ReviewDecision.REVISE_AND_REVIEW),
        (ReviewDecision.REJECT_AND_REPLACE, ReviewDecision.READY_FOR_REVIEW),
    ],
)
def test_illegal_review_transitions(
    previous: ReviewDecision,
    new: ReviewDecision,
) -> None:
    with pytest.raises(ValueError, match="illegal review transition"):
        validate_review_transition(previous, new)
