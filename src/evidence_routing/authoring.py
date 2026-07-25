"""Versioned records for path-blind question authoring and manual corpus checks."""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from evidence_routing.schemas import (
    ConstructionCategory,
    Domain,
    Identifier,
    StrictModel,
)


class ReviewDecision(StrEnum):
    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    ACCEPT = "accept"
    REVISE_AND_REVIEW = "revise_and_review"
    REJECT_AND_REPLACE = "reject_and_replace"


class PriorQuestionCheck(StrEnum):
    NOT_CHECKED = "not_checked"
    CLEAR = "clear"
    REVIEW_REQUIRED = "review_required"


class SearchConclusion(StrEnum):
    CORPUS_SUFFICIENT = "corpus_sufficient"
    CORPUS_INSUFFICIENT = "corpus_insufficient"


class AuthoringRecord(StrictModel):
    authoring_id: Identifier
    question_id: Identifier
    specification_id: Identifier
    domain: Domain
    construction_category: ConstructionCategory
    review_decision: ReviewDecision = ReviewDecision.DRAFT
    construction_rationale: str = Field(min_length=10, max_length=1000)
    counter_cue_justification: str | None = Field(default=None, max_length=500)
    prior_question_check: PriorQuestionCheck = PriorQuestionCheck.NOT_CHECKED
    source_resolution_checked: bool = False
    manual_search_record_id: Identifier | None = None
    reviewed_by: Identifier | None = None
    reviewed_at: datetime | None = None

    @model_validator(mode="after")
    def accepted_record_is_complete(self) -> AuthoringRecord:
        if (self.reviewed_by is None) != (self.reviewed_at is None):
            raise ValueError("reviewed_by and reviewed_at must be supplied together")
        if self.reviewed_at is not None and self.reviewed_at.utcoffset() is None:
            raise ValueError("reviewed_at must include a timezone")
        if self.review_decision == ReviewDecision.ACCEPT:
            if not self.source_resolution_checked:
                raise ValueError("accepted records require resolved source identifiers")
            if self.prior_question_check != PriorQuestionCheck.CLEAR:
                raise ValueError("accepted records require a clear prior-question check")
            if self.reviewed_by is None:
                raise ValueError("accepted records require reviewer details")
            if (
                self.construction_category
                == ConstructionCategory.EVIDENCE_INSUFFICIENT
                and self.manual_search_record_id is None
            ):
                raise ValueError(
                    "accepted evidence-insufficient records require a manual search record"
                )
        if (
            self.construction_category != ConstructionCategory.EVIDENCE_INSUFFICIENT
            and self.manual_search_record_id is not None
        ):
            raise ValueError(
                "manual_search_record_id is reserved for evidence-insufficient candidates"
            )
        return self


class ManualSearchRecord(StrictModel):
    manual_search_id: Identifier
    question_id: Identifier
    domain: Domain
    checked_by: Identifier
    checked_at: datetime
    search_scope: str = Field(min_length=10, max_length=1000)
    search_methods: list[
        Literal[
            "identifier_lookup",
            "title_lookup",
            "full_text_search",
            "graph_relation_check",
            "manual_document_browse",
        ]
    ] = Field(min_length=1, max_length=5)
    query_terms: list[str] = Field(min_length=1, max_length=20)
    evidence_found: bool
    conclusion: SearchConclusion
    rationale: str = Field(min_length=10, max_length=1000)

    @model_validator(mode="after")
    def search_result_is_consistent(self) -> ManualSearchRecord:
        if self.checked_at.utcoffset() is None:
            raise ValueError("checked_at must include a timezone")
        if len(set(self.search_methods)) != len(self.search_methods):
            raise ValueError("search_methods must be unique")
        normalized_terms = [term.strip().casefold() for term in self.query_terms]
        if any(not term for term in normalized_terms):
            raise ValueError("query_terms cannot contain empty values")
        if len(set(normalized_terms)) != len(normalized_terms):
            raise ValueError("query_terms must be unique after normalization")
        expected = (
            SearchConclusion.CORPUS_SUFFICIENT
            if self.evidence_found
            else SearchConclusion.CORPUS_INSUFFICIENT
        )
        if self.conclusion != expected:
            raise ValueError("conclusion must match evidence_found")
        return self


_ALLOWED_REVIEW_TRANSITIONS = {
    ReviewDecision.DRAFT: {ReviewDecision.READY_FOR_REVIEW},
    ReviewDecision.READY_FOR_REVIEW: {
        ReviewDecision.ACCEPT,
        ReviewDecision.REVISE_AND_REVIEW,
        ReviewDecision.REJECT_AND_REPLACE,
    },
    ReviewDecision.REVISE_AND_REVIEW: {ReviewDecision.READY_FOR_REVIEW},
    ReviewDecision.ACCEPT: set(),
    ReviewDecision.REJECT_AND_REPLACE: set(),
}


def validate_review_transition(
    previous: ReviewDecision,
    new: ReviewDecision,
) -> None:
    """Reject review-state jumps and changes to terminal decisions."""
    if new == previous:
        return
    if new not in _ALLOWED_REVIEW_TRANSITIONS[previous]:
        raise ValueError(f"illegal review transition: {previous.value} -> {new.value}")


AUTHORING_SCHEMA_MODELS: dict[str, type[StrictModel]] = {
    "authoring-record": AuthoringRecord,
    "manual-search-record": ManualSearchRecord,
}


def export_authoring_json_schemas(destination: Path) -> list[Path]:
    """Write deterministic JSON Schemas for the authoring records."""
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in sorted(AUTHORING_SCHEMA_MODELS.items()):
        path = destination / f"{name}-v1.schema.json"
        payload: dict[str, Any] = model.model_json_schema()
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written
