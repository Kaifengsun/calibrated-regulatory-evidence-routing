"""Tamper-evident pre-freeze question review payloads and workbook round trips."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from evidence_routing.authoring import (
    AuthoringRecord,
    PriorQuestionCheck,
    ReviewDecision,
    validate_review_transition,
)
from evidence_routing.schemas import EvidenceSpecification, QueryRecord

WorkbookWriter = Callable[[Path, dict[str, Any]], None]
WorkbookReader = Callable[[Path], list[dict[str, Any]]]

IMMUTABLE_REVIEW_FIELDS = (
    "question_id",
    "specification_id",
    "authoring_id",
    "domain",
    "language",
    "construction_category",
    "query_text",
    "source_group_id",
    "authoring_source_ids",
    "required_source_ids",
    "sufficient_source_ids",
    "insufficiency_candidate",
    "evidence_scope_note",
    "counter_cue_tags",
    "construction_rationale",
    "counter_cue_justification",
    "manual_search_record_id",
    "source_resolution_checked",
    "prior_question_check",
)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _identity_hash(row: Mapping[str, Any]) -> str:
    payload = {field: row[field] for field in IMMUTABLE_REVIEW_FIELDS}
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def build_prefreeze_review_payload(
    queries: list[QueryRecord],
    specifications: list[EvidenceSpecification],
    authoring_records: list[AuthoringRecord],
    *,
    evidence_previews: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Build deterministic rows; previews are private display-only fields."""
    specification_by_question = {
        row.question_id: row for row in specifications
    }
    authoring_by_question = {row.question_id: row for row in authoring_records}
    identities = (
        {row.question_id for row in queries},
        set(specification_by_question),
        set(authoring_by_question),
    )
    if len({frozenset(values) for values in identities}) != 1:
        raise ValueError("query, specification, and authoring question IDs differ")

    rows = []
    for query in sorted(
        queries,
        key=lambda row: (
            row.domain.value,
            row.construction_category.value,
            row.question_id,
        ),
    ):
        specification = specification_by_question[query.question_id]
        authoring = authoring_by_question[query.question_id]
        if authoring.specification_id != specification.specification_id:
            raise ValueError(f"specification mismatch for {query.question_id}")
        row: dict[str, Any] = {
            "question_id": query.question_id,
            "specification_id": specification.specification_id,
            "authoring_id": authoring.authoring_id,
            "domain": query.domain.value,
            "language": query.language,
            "construction_category": query.construction_category.value,
            "query_text": query.query_text,
            "source_group_id": query.source_group_id,
            "authoring_source_ids": list(query.authoring_source_ids),
            "required_source_ids": list(specification.required_source_ids),
            "sufficient_source_ids": list(specification.sufficient_source_ids),
            "insufficiency_candidate": specification.insufficiency_candidate,
            "evidence_scope_note": specification.evidence_scope_note,
            "counter_cue_tags": list(query.counter_cue_tags),
            "construction_rationale": authoring.construction_rationale,
            "counter_cue_justification": authoring.counter_cue_justification,
            "manual_search_record_id": authoring.manual_search_record_id,
            "source_resolution_checked": authoring.source_resolution_checked,
            "prior_question_check": authoring.prior_question_check.value,
            "evidence_preview": dict(
                (evidence_previews or {}).get(query.question_id, {})
            ),
            "review_decision": "",
            "reviewer_comment": "",
            "evidence_complete": "",
            "category_correct": "",
            "wording_natural": "",
            "prior_overlap_clear": "",
        }
        row["identity_sha256"] = _identity_hash(row)
        rows.append(row)
    return {
        "schema_version": "1.0",
        "immutable_fields": list(IMMUTABLE_REVIEW_FIELDS),
        "rows": rows,
    }


def export_prefreeze_review(
    destination: Path,
    queries: list[QueryRecord],
    specifications: list[EvidenceSpecification],
    authoring_records: list[AuthoringRecord],
    *,
    workbook_writer: WorkbookWriter,
    evidence_previews: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Export a private XLSX using the supplied spreadsheet-runtime writer."""
    payload = build_prefreeze_review_payload(
        queries,
        specifications,
        authoring_records,
        evidence_previews=evidence_previews,
    )
    workbook_writer(destination, payload)
    return payload


def import_prefreeze_review(
    workbook: Path,
    baseline_payload: Mapping[str, Any],
    authoring_records: list[AuthoringRecord],
    *,
    workbook_reader: WorkbookReader,
    reviewer_id: str,
    reviewed_at: datetime,
) -> list[AuthoringRecord]:
    """Validate immutable cells and apply explicit review decisions."""
    if reviewed_at.utcoffset() is None:
        raise ValueError("reviewed_at must include a timezone")
    baseline_rows = {
        str(row["question_id"]): row for row in baseline_payload["rows"]
    }
    imported_rows = {
        str(row["question_id"]): row for row in workbook_reader(workbook)
    }
    if set(imported_rows) != set(baseline_rows):
        raise ValueError("review workbook question identities differ")
    authoring_by_question = {row.question_id: row for row in authoring_records}
    if set(authoring_by_question) != set(baseline_rows):
        raise ValueError("authoring records differ from review baseline")

    updated = []
    for question_id in sorted(baseline_rows):
        baseline = baseline_rows[question_id]
        imported = imported_rows[question_id]
        for field in IMMUTABLE_REVIEW_FIELDS:
            if imported.get(field) != baseline.get(field):
                raise ValueError(
                    f"immutable review field changed: {question_id}.{field}"
                )
        if imported.get("identity_sha256") != baseline.get("identity_sha256"):
            raise ValueError(f"review identity hash changed: {question_id}")
        if _identity_hash(imported) != baseline["identity_sha256"]:
            raise ValueError(f"review identity content changed: {question_id}")
        raw_decision = str(imported.get("review_decision") or "").strip()
        try:
            decision = ReviewDecision(raw_decision)
        except ValueError as error:
            raise ValueError(
                f"invalid review decision for {question_id}: {raw_decision!r}"
            ) from error
        previous = authoring_by_question[question_id]
        validate_review_transition(previous.review_decision, decision)
        changes: dict[str, Any] = {"review_decision": decision}
        if decision == ReviewDecision.ACCEPT:
            checklist = (
                "evidence_complete",
                "category_correct",
                "wording_natural",
                "prior_overlap_clear",
            )
            if any(
                str(imported.get(field) or "").strip().casefold() != "yes"
                for field in checklist
            ):
                raise ValueError(
                    f"accepted review has an incomplete checklist: {question_id}"
                )
            changes.update(
                {
                    "prior_question_check": PriorQuestionCheck.CLEAR,
                    "reviewed_by": reviewer_id,
                    "reviewed_at": reviewed_at,
                }
            )
        updated.append(
            AuthoringRecord.model_validate(
                {
                    **previous.model_dump(mode="python"),
                    **changes,
                }
            )
        )
    return updated
