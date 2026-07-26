"""Deterministic method-blinded evidence annotation workbook round trips."""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from sklearn.metrics import cohen_kappa_score, confusion_matrix

from evidence_routing.schemas import (
    AnnotationRole,
    ConstructionCategory,
    Domain,
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


def select_duplicate_questions(
    queries: Sequence[QueryRecord],
    *,
    quotas: Mapping[str, Mapping[str, int]],
    seed: int,
) -> list[str]:
    """Select complete-question duplicate-review units by frozen stratum quotas."""
    query_by_id = {query.question_id: query for query in queries}
    if len(query_by_id) != len(queries):
        raise ValueError("query identities must be unique")

    expected_domains = {domain.value for domain in Domain}
    if set(quotas) != expected_domains:
        raise ValueError("duplicate-review quotas must define both frozen domains")

    selections: list[str] = []
    for domain in Domain:
        domain_quotas = quotas[domain.value]
        expected_categories = {category.value for category in ConstructionCategory}
        if set(domain_quotas) != expected_categories:
            raise ValueError(
                f"duplicate-review quotas must define every category for {domain.value}"
            )
        for category in ConstructionCategory:
            quota = domain_quotas[category.value]
            if isinstance(quota, bool) or not isinstance(quota, int) or quota < 0:
                raise ValueError(
                    f"invalid duplicate-review quota: {domain.value}/{category.value}"
                )
            candidates = sorted(
                query.question_id
                for query in queries
                if query.domain == domain
                and query.construction_category == category
            )
            if len(candidates) < quota:
                raise ValueError(
                    f"duplicate-review quota exceeds available questions: "
                    f"{domain.value}/{category.value}"
                )
            ranked = sorted(
                candidates,
                key=lambda question_id: (
                    hashlib.sha256(
                        (
                            f"{seed}\0{domain.value}\0{category.value}"
                            f"\0{question_id}"
                        ).encode()
                    ).hexdigest(),
                    question_id,
                ),
            )
            selections.extend(ranked[:quota])

    return sorted(selections)


def _collapse_annotation_occurrences(
    annotations: Sequence[EvidenceAnnotation],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    collapsed: dict[tuple[str, str, str], dict[str, Any]] = {}
    for annotation in annotations:
        key = (
            annotation.question_id,
            annotation.evidence_kind,
            annotation.evidence_id,
        )
        record = collapsed.setdefault(
            key,
            {
                "question_id": annotation.question_id,
                "evidence_kind": annotation.evidence_kind,
                "evidence_id": annotation.evidence_id,
                "label": annotation.label,
                "harmful_reason_code": annotation.harmful_reason_code,
                "annotation_ids": [],
                "path_ids": [],
            },
        )
        if (
            record["label"] != annotation.label
            or record["harmful_reason_code"] != annotation.harmful_reason_code
        ):
            raise ValueError(f"inconsistent repeated annotation label: {key}")
        record["annotation_ids"].append(annotation.annotation_id)
        record["path_ids"].append(annotation.path_id.value)
    for record in collapsed.values():
        record["annotation_ids"] = sorted(set(record["annotation_ids"]))
        record["path_ids"] = sorted(set(record["path_ids"]))
    return collapsed


def _nominal_kappa(
    primary_labels: Sequence[str],
    duplicate_labels: Sequence[str],
    *,
    labels: Sequence[str],
) -> float | None:
    if len(set(primary_labels) | set(duplicate_labels)) < 2:
        return None
    value = float(cohen_kappa_score(primary_labels, duplicate_labels, labels=labels))
    return value if value == value else None


def compute_agreement(
    primary_annotations: Sequence[EvidenceAnnotation],
    duplicate_annotations: Sequence[EvidenceAnnotation],
    *,
    duplicate_identity_mapping: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute nominal agreement once per unique question-evidence unit."""
    if duplicate_identity_mapping is not None:
        return _compute_row_level_agreement(
            primary_annotations,
            duplicate_annotations,
            duplicate_identity_mapping,
        )
    primary = _collapse_annotation_occurrences(primary_annotations)
    duplicate = _collapse_annotation_occurrences(duplicate_annotations)
    if not duplicate:
        raise ValueError("duplicate annotations are empty")
    if not set(duplicate).issubset(primary):
        raise ValueError("duplicate annotations contain units absent from primary labels")

    comparisons = []
    for key in sorted(duplicate):
        primary_row = primary[key]
        duplicate_row = duplicate[key]
        comparisons.append(
            {
                "question_id": key[0],
                "evidence_kind": key[1],
                "evidence_id": key[2],
                "path_ids": duplicate_row["path_ids"],
                "primary_annotation_ids": primary_row["annotation_ids"],
                "duplicate_annotation_ids": duplicate_row["annotation_ids"],
                "primary_label": primary_row["label"].value,
                "duplicate_label": duplicate_row["label"].value,
                "primary_harmful_reason_code": primary_row["harmful_reason_code"],
                "duplicate_harmful_reason_code": duplicate_row[
                    "harmful_reason_code"
                ],
                "agrees": primary_row["label"] == duplicate_row["label"],
                "harmful_reason_agrees": (
                    primary_row["harmful_reason_code"]
                    == duplicate_row["harmful_reason_code"]
                ),
            }
        )

    return _summarize_comparisons(comparisons, unit="unique_question_evidence")


def _compute_row_level_agreement(
    primary_annotations: Sequence[EvidenceAnnotation],
    duplicate_annotations: Sequence[EvidenceAnnotation],
    duplicate_identity_mapping: Mapping[str, Any],
) -> dict[str, Any]:
    primary_by_occurrence = {
        (
            annotation.question_id,
            annotation.path_id.value,
            annotation.evidence_id,
            annotation.evidence_kind,
        ): annotation
        for annotation in primary_annotations
    }
    duplicate_by_occurrence = {
        (
            annotation.question_id,
            annotation.path_id.value,
            annotation.evidence_id,
            annotation.evidence_kind,
        ): annotation
        for annotation in duplicate_annotations
    }
    comparisons = []
    for mapping_row in sorted(
        duplicate_identity_mapping["row_mappings"],
        key=lambda row: row["row_code"],
    ):
        occurrence_keys = [
            (
                occurrence["question_id"],
                occurrence["path_id"],
                occurrence["evidence_id"],
                occurrence["evidence_kind"],
            )
            for occurrence in mapping_row["occurrences"]
        ]
        try:
            primary_rows = [primary_by_occurrence[key] for key in occurrence_keys]
            duplicate_rows = [duplicate_by_occurrence[key] for key in occurrence_keys]
        except KeyError as error:
            raise ValueError(
                f"annotation occurrence missing for duplicate row {mapping_row['row_code']}"
            ) from error
        primary_labels = {row.label for row in primary_rows}
        primary_reasons = {row.harmful_reason_code for row in primary_rows}
        duplicate_labels = {row.label for row in duplicate_rows}
        duplicate_reasons = {row.harmful_reason_code for row in duplicate_rows}
        if (
            len(primary_labels) != 1
            or len(primary_reasons) != 1
            or len(duplicate_labels) != 1
            or len(duplicate_reasons) != 1
        ):
            raise ValueError(
                f"inconsistent labels within duplicate workbook row: "
                f"{mapping_row['row_code']}"
            )
        primary_label = next(iter(primary_labels))
        duplicate_label = next(iter(duplicate_labels))
        primary_reason = next(iter(primary_reasons))
        duplicate_reason = next(iter(duplicate_reasons))
        comparisons.append(
            {
                "duplicate_row_code": mapping_row["row_code"],
                "question_id": occurrence_keys[0][0],
                "evidence_kind": occurrence_keys[0][3],
                "evidence_id": occurrence_keys[0][2],
                "evidence_ids": sorted({key[2] for key in occurrence_keys}),
                "path_ids": sorted({key[1] for key in occurrence_keys}),
                "primary_annotation_ids": sorted(
                    {row.annotation_id for row in primary_rows}
                ),
                "duplicate_annotation_ids": sorted(
                    {row.annotation_id for row in duplicate_rows}
                ),
                "primary_label": primary_label.value,
                "duplicate_label": duplicate_label.value,
                "primary_harmful_reason_code": primary_reason,
                "duplicate_harmful_reason_code": duplicate_reason,
                "agrees": primary_label == duplicate_label,
                "harmful_reason_agrees": primary_reason == duplicate_reason,
            }
        )
    return _summarize_comparisons(comparisons, unit="workbook_visible_evidence_row")


def _summarize_comparisons(
    comparisons: list[dict[str, Any]],
    *,
    unit: str,
) -> dict[str, Any]:
    labels = [label.value for label in EvidenceLabel]
    primary_labels = [row["primary_label"] for row in comparisons]
    duplicate_labels = [row["duplicate_label"] for row in comparisons]
    agreement_count = sum(row["agrees"] for row in comparisons)
    matrix = confusion_matrix(primary_labels, duplicate_labels, labels=labels)
    kappa = _nominal_kappa(primary_labels, duplicate_labels, labels=labels)
    primary_counts = Counter(primary_labels)
    duplicate_counts = Counter(duplicate_labels)
    per_label = {}
    for label in labels:
        both = sum(
            row["primary_label"] == label and row["duplicate_label"] == label
            for row in comparisons
        )
        denominator = primary_counts[label] + duplicate_counts[label]
        per_label[label] = {
            "primary_count": primary_counts[label],
            "duplicate_count": duplicate_counts[label],
            "both_count": both,
            "specific_agreement": (2 * both / denominator) if denominator else None,
        }
    return {
        "unit": unit,
        "pair_count": len(comparisons),
        "question_count": len({row["question_id"] for row in comparisons}),
        "agreement_count": agreement_count,
        "disagreement_count": len(comparisons) - agreement_count,
        "exact_agreement": agreement_count / len(comparisons),
        "cohen_kappa": kappa,
        "label_order": labels,
        "confusion_matrix": matrix.tolist(),
        "per_label": per_label,
        "comparisons": comparisons,
    }


def build_adjudication_queue(agreement: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Create one immutable queue row for each unique-unit label disagreement."""
    queue = []
    for row in agreement["comparisons"]:
        label_disagreement = not row["agrees"]
        reason_disagreement = (
            row["primary_label"] == EvidenceLabel.HARMFUL.value
            and row["duplicate_label"] == EvidenceLabel.HARMFUL.value
            and not row["harmful_reason_agrees"]
        )
        if not label_disagreement and not reason_disagreement:
            continue
        identity = (
            f"{row['question_id']}\0{row['evidence_kind']}\0"
            f"{row.get('duplicate_row_code', row['evidence_id'])}"
        )
        queue.append(
            {
                "queue_id": f"ADJQ-{hashlib.sha256(identity.encode()).hexdigest()[:16]}",
                "question_id": row["question_id"],
                "duplicate_row_code": row.get("duplicate_row_code"),
                "evidence_kind": row["evidence_kind"],
                "evidence_id": row["evidence_id"],
                "evidence_ids": row.get("evidence_ids", [row["evidence_id"]]),
                "path_ids": row["path_ids"],
                "primary_annotation_ids": row["primary_annotation_ids"],
                "duplicate_annotation_ids": row["duplicate_annotation_ids"],
                "primary_label": row["primary_label"],
                "duplicate_label": row["duplicate_label"],
                "primary_harmful_reason_code": row[
                    "primary_harmful_reason_code"
                ],
                "duplicate_harmful_reason_code": row[
                    "duplicate_harmful_reason_code"
                ],
                "queue_reason": (
                    "label_disagreement"
                    if label_disagreement
                    else "harmful_reason_disagreement"
                ),
            }
        )
    return queue


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
