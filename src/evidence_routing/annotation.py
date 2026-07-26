"""Deterministic method-blinded evidence annotation workbook round trips."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from evidence_routing.schemas import (
    AnnotationRole,
    EvidenceAnnotation,
    EvidenceLabel,
    ExecutionStatus,
    PathId,
    PathRun,
    QueryRecord,
)

WorkbookWriter = Callable[[Path, dict[str, Any]], None]
WorkbookReader = Callable[[Path], list[dict[str, Any]]]
EvidenceTextLookup = Callable[
    [PathRun, str, str],
    Mapping[str, str],
]

_HARMFUL_REASONS = {
    "wrong_version",
    "wrong_regulated_object",
    "wrong_scope_condition_or_exception",
    "direct_conflict",
    "materially_misleading",
}
_VISIBLE_IDENTITY_FIELDS = (
    "row_code",
    "question_code",
    "package_codes",
    "question_text",
    "package_positions",
    "evidence_kind",
    "source_id",
    "document_id",
    "heading",
    "context_type",
    "evidence_text",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _identity_hash(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        _canonical({field: row.get(field) for field in _VISIBLE_IDENTITY_FIELDS})
    ).hexdigest()


def build_blinded_annotation_payload(
    queries: Sequence[QueryRecord],
    path_runs: Sequence[PathRun],
    *,
    evidence_text_lookup: EvidenceTextLookup,
    seed: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build workbook-visible rows and a separate path-identity mapping."""
    query_by_id = {row.question_id: row for row in queries}
    if len(query_by_id) != len(queries):
        raise ValueError("query identities must be unique")
    runs_by_question: dict[str, list[PathRun]] = {
        question_id: [] for question_id in query_by_id
    }
    for run in path_runs:
        if run.question_id not in runs_by_question:
            raise ValueError(f"path run has no frozen query: {run.question_id}")
        runs_by_question[run.question_id].append(run)
    for question_id, runs in runs_by_question.items():
        if {row.path_id for row in runs} != set(PathId) or len(runs) != 6:
            raise ValueError(f"question does not have exactly P0-P5: {question_id}")

    generator = random.Random(seed)
    question_ids = sorted(query_by_id)
    shuffled_questions = question_ids.copy()
    generator.shuffle(shuffled_questions)
    question_codes = {
        question_id: f"Q-{index:03d}"
        for index, question_id in enumerate(shuffled_questions, 1)
    }
    rows: list[dict[str, Any]] = []
    package_mappings: list[dict[str, str]] = []
    evidence_records: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    package_number = 0

    for question_id in sorted(question_ids, key=question_codes.get):
        query = query_by_id[question_id]
        runs = sorted(runs_by_question[question_id], key=lambda row: row.path_id.value)
        generator.shuffle(runs)
        for run in runs:
            package_number += 1
            package_code = f"PKG-{package_number:03d}"
            package_mappings.append(
                {
                    "package_code": package_code,
                    "question_id": question_id,
                    "run_id": run.run_id,
                    "path_id": run.path_id.value,
                    "status": run.status.value,
                }
            )
            units: list[tuple[str, str, int, str, str, str | None]] = []
            for unit in run.ranked_units:
                units.append(
                    (
                        "ranked",
                        unit.source_id,
                        unit.rank,
                        unit.source_id,
                        unit.document_id,
                        None,
                    )
                )
            for index, sidecar in enumerate(run.context_sidecars, 1):
                units.append(
                    (
                        "sidecar",
                        sidecar.sidecar_id,
                        len(run.ranked_units) + index,
                        sidecar.source_id,
                        sidecar.document_id,
                        sidecar.context_type.value,
                    )
                )
            if run.status == ExecutionStatus.EXECUTION_ERROR and units:
                raise ValueError(f"execution-error run contains evidence: {run.run_id}")
            for evidence_kind, evidence_id, order, source_id, document_id, context_type in units:
                display = dict(evidence_text_lookup(run, evidence_kind, evidence_id))
                key = (
                    question_id,
                    evidence_kind,
                    source_id,
                    context_type or "",
                )
                visible = {
                    "question_code": question_codes[question_id],
                    "question_text": query.query_text,
                    "evidence_kind": evidence_kind,
                    "source_id": source_id,
                    "document_id": document_id,
                    "heading": str(display.get("heading", "")),
                    "context_type": context_type or "",
                    "evidence_text": str(display.get("evidence_text", "")),
                }
                if not visible["evidence_text"].strip():
                    raise ValueError(
                        f"annotation evidence text is empty: {run.run_id}/{evidence_id}"
                    )
                record = evidence_records.setdefault(
                    key,
                    {
                        "visible": visible,
                        "memberships": [],
                        "occurrences": [],
                    },
                )
                if record["visible"] != visible:
                    raise ValueError(
                        f"inconsistent display text for repeated evidence: {key}"
                    )
                record["memberships"].append(
                    {"package_code": package_code, "item_order": order}
                )
                record["occurrences"].append(
                    {
                        "question_id": question_id,
                        "run_id": run.run_id,
                        "path_id": run.path_id.value,
                        "evidence_id": evidence_id,
                        "evidence_kind": evidence_kind,
                    }
                )

    row_mappings: list[dict[str, Any]] = []
    ordered_records = sorted(
        evidence_records.values(),
        key=lambda record: (
            record["visible"]["question_code"],
            min(
                int(item["package_code"].split("-")[1])
                for item in record["memberships"]
            ),
            min(item["item_order"] for item in record["memberships"]),
            record["visible"]["evidence_kind"],
            record["visible"]["source_id"],
        ),
    )
    for row_number, record in enumerate(ordered_records, 1):
        memberships = sorted(
            record["memberships"],
            key=lambda item: (item["package_code"], item["item_order"]),
        )
        row = {
            "row_code": f"EV-{row_number:05d}",
            **record["visible"],
            "package_codes": " | ".join(
                item["package_code"] for item in memberships
            ),
            "package_positions": " | ".join(
                f"{item['package_code']}:{item['item_order']}"
                for item in memberships
            ),
            "label": "",
            "harmful_reason_code": "",
            "annotator_comment": "",
        }
        row["identity_sha256"] = _identity_hash(row)
        rows.append(row)
        row_mappings.append(
            {
                "row_code": row["row_code"],
                "identity_sha256": row["identity_sha256"],
                "occurrences": sorted(
                    record["occurrences"],
                    key=lambda item: (
                        item["run_id"],
                        item["evidence_kind"],
                        item["evidence_id"],
                    ),
                ),
            }
        )
    workbook_payload = {
        "schema_version": "1.0",
        "seed": seed,
        "rows": rows,
        "packages": [
            {
                "package_code": row["package_code"],
                "question_code": question_codes[row["question_id"]],
                "question_text": query_by_id[row["question_id"]].query_text,
                "item_count": sum(
                    row["package_code"]
                    in item["package_codes"].split(" | ")
                    for item in rows
                ),
            }
            for row in package_mappings
        ],
    }
    mapping = {
        "schema_version": "1.0",
        "seed": seed,
        "package_mappings": package_mappings,
        "row_mappings": row_mappings,
    }
    return workbook_payload, mapping


def export_blinded_workbook(
    destination: Path,
    mapping_destination: Path,
    queries: Sequence[QueryRecord],
    path_runs: Sequence[PathRun],
    *,
    evidence_text_lookup: EvidenceTextLookup,
    seed: int,
    workbook_writer: WorkbookWriter,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Export visible evidence separately from the ignored method mapping."""
    payload, mapping = build_blinded_annotation_payload(
        queries,
        path_runs,
        evidence_text_lookup=evidence_text_lookup,
        seed=seed,
    )
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite annotation workbook: {destination}")
    if mapping_destination.exists():
        raise FileExistsError(f"refusing to overwrite identity mapping: {mapping_destination}")
    workbook_writer(destination, payload)
    mapping_destination.parent.mkdir(parents=True, exist_ok=True)
    mapping_destination.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload, mapping


def import_reviewed_workbook(
    workbook: Path,
    baseline_payload: Mapping[str, Any],
    identity_mapping: Mapping[str, Any],
    *,
    workbook_reader: WorkbookReader,
    annotator_code: str,
    annotated_at: datetime,
    annotation_role: AnnotationRole = AnnotationRole.PRIMARY,
) -> list[EvidenceAnnotation]:
    """Validate visible identities and preserve one raw label per workbook row."""
    if annotated_at.utcoffset() is None:
        raise ValueError("annotated_at must include a timezone")
    baseline_rows = {
        str(row["row_code"]): row for row in baseline_payload["rows"]
    }
    imported_rows = {
        str(row["row_code"]): row for row in workbook_reader(workbook)
    }
    mapping_rows = {
        str(row["row_code"]): row for row in identity_mapping["row_mappings"]
    }
    if set(imported_rows) != set(baseline_rows) or set(mapping_rows) != set(
        baseline_rows
    ):
        raise ValueError("annotation workbook row identities differ")

    annotations: list[EvidenceAnnotation] = []
    for row_code in sorted(baseline_rows):
        baseline = baseline_rows[row_code]
        imported = imported_rows[row_code]
        mapping = mapping_rows[row_code]
        for field in _VISIBLE_IDENTITY_FIELDS:
            if imported.get(field) != baseline.get(field):
                raise ValueError(f"immutable annotation field changed: {row_code}.{field}")
        if (
            imported.get("identity_sha256") != baseline.get("identity_sha256")
            or mapping.get("identity_sha256") != baseline.get("identity_sha256")
            or _identity_hash(imported) != baseline.get("identity_sha256")
        ):
            raise ValueError(f"annotation identity hash changed: {row_code}")
        raw_label = str(imported.get("label") or "").strip().upper()
        try:
            label = EvidenceLabel(raw_label)
        except ValueError as error:
            raise ValueError(f"invalid evidence label: {row_code}/{raw_label!r}") from error
        harmful_reason = str(
            imported.get("harmful_reason_code") or ""
        ).strip()
        if label == EvidenceLabel.HARMFUL:
            if harmful_reason not in _HARMFUL_REASONS:
                raise ValueError(f"HARMFUL row lacks a valid reason: {row_code}")
        elif harmful_reason:
            raise ValueError(f"non-HARMFUL row has a harmful reason: {row_code}")
        for occurrence_index, occurrence in enumerate(
            mapping["occurrences"], 1
        ):
            annotations.append(
                EvidenceAnnotation(
                    annotation_id=(
                        f"ANN-{annotator_code}-{row_code}-{occurrence_index:02d}"
                    ),
                    question_id=occurrence["question_id"],
                    path_id=occurrence["path_id"],
                    evidence_id=occurrence["evidence_id"],
                    evidence_kind=occurrence["evidence_kind"],
                    label=label,
                    annotation_role=annotation_role,
                    annotator_code=annotator_code,
                    annotated_at=annotated_at,
                    harmful_reason_code=harmful_reason or None,
                )
            )
    return annotations
