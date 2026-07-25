"""Cross-record validation with stable, machine-readable error codes."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from evidence_routing.schemas import (
    ConstructionCategory,
    Domain,
    EvidenceSpecification,
    ExperimentManifest,
    PathId,
    PathRun,
    QueryRecord,
    QuestionAnnotationBundle,
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


class DatasetValidationError(ValueError):
    def __init__(self, issues: Iterable[ValidationIssue]) -> None:
        self.issues = tuple(sorted(issues, key=lambda item: (item.code, item.message)))
        rendered = "; ".join(f"{item.code}: {item.message}" for item in self.issues)
        super().__init__(rendered)


FROZEN_QUESTION_QUOTAS: dict[tuple[Domain, ConstructionCategory], int] = {
    (Domain.CHEMICAL, ConstructionCategory.DIRECT_CLAUSE): 12,
    (Domain.CHEMICAL, ConstructionCategory.PARENT_HEADING_CONTEXT): 12,
    (Domain.CHEMICAL, ConstructionCategory.TABLE_RELATED): 12,
    (Domain.CHEMICAL, ConstructionCategory.CITATION_DEPENDENCY): 12,
    (Domain.CHEMICAL, ConstructionCategory.EVIDENCE_INSUFFICIENT): 12,
    (Domain.PHARMACEUTICAL, ConstructionCategory.DIRECT_CLAUSE): 15,
    (Domain.PHARMACEUTICAL, ConstructionCategory.PARENT_HEADING_CONTEXT): 15,
    (Domain.PHARMACEUTICAL, ConstructionCategory.TABLE_RELATED): 15,
    (Domain.PHARMACEUTICAL, ConstructionCategory.CITATION_DEPENDENCY): 0,
    (Domain.PHARMACEUTICAL, ConstructionCategory.EVIDENCE_INSUFFICIENT): 15,
}


def _duplicates(values: Iterable[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def validate_dataset(
    queries: list[QueryRecord],
    specifications: list[EvidenceSpecification],
    *,
    require_frozen_counts: bool = True,
    expected_quotas: Mapping[tuple[Domain, ConstructionCategory], int] | None = None,
) -> None:
    issues: list[ValidationIssue] = []
    duplicate_questions = _duplicates(row.question_id for row in queries)
    if duplicate_questions:
        issues.append(ValidationIssue("E_QUERY_ID_DUPLICATE", ",".join(duplicate_questions)))
    duplicate_specs = _duplicates(row.question_id for row in specifications)
    if duplicate_specs:
        issues.append(ValidationIssue("E_SPEC_ID_DUPLICATE", ",".join(duplicate_specs)))
    query_ids = {row.question_id for row in queries}
    spec_ids = {row.question_id for row in specifications}
    if query_ids != spec_ids:
        issues.append(
            ValidationIssue(
                "E_QUERY_SPEC_MISMATCH",
                f"queries_only={sorted(query_ids - spec_ids)}; "
                f"specifications_only={sorted(spec_ids - query_ids)}",
            )
        )
    if require_frozen_counts:
        expected = dict(
            FROZEN_QUESTION_QUOTAS if expected_quotas is None else expected_quotas
        )
        required_keys = {
            (domain, category) for domain in Domain for category in ConstructionCategory
        }
        if set(expected) != required_keys or any(count < 0 for count in expected.values()):
            raise ValueError("expected_quotas must define non-negative counts for all cells")
        expected_total = sum(expected.values())
        if len(queries) != expected_total:
            issues.append(
                ValidationIssue(
                    "E_PILOT_COUNT",
                    f"expected={expected_total}; actual={len(queries)}",
                )
            )
        actual = Counter((row.domain, row.construction_category) for row in queries)
        for key, expected_count in expected.items():
            if actual[key] != expected_count:
                issues.append(
                    ValidationIssue(
                        "E_CATEGORY_QUOTA",
                        f"domain={key[0].value}; category={key[1].value}; "
                        f"expected={expected_count}; actual={actual[key]}",
                    )
                )
    if issues:
        raise DatasetValidationError(issues)


def validate_path_run(run: PathRun) -> None:
    issues: list[ValidationIssue] = []
    ranks = [row.rank for row in run.ranked_units]
    if ranks != list(range(1, len(ranks) + 1)):
        issues.append(ValidationIssue("E_RANK_SEQUENCE", f"ranks={ranks}"))
    duplicate_units = _duplicates(row.source_id for row in run.ranked_units)
    if duplicate_units:
        issues.append(ValidationIssue("E_EVIDENCE_ID_DUPLICATE", ",".join(duplicate_units)))
    sidecar_ids = [row.sidecar_id for row in run.context_sidecars]
    duplicate_sidecars = _duplicates(sidecar_ids)
    if duplicate_sidecars:
        issues.append(ValidationIssue("E_SIDECAR_ID_DUPLICATE", ",".join(duplicate_sidecars)))
    if run.path_id in {PathId.P0, PathId.P1, PathId.P3} and run.context_sidecars:
        issues.append(ValidationIssue("E_PATH_CONTEXT_FORBIDDEN", f"path={run.path_id.value}"))
    if run.path_id in {PathId.P0, PathId.P1, PathId.P2, PathId.P4} and any(
        row.origin.value == "graph" for row in run.ranked_units
    ):
        issues.append(ValidationIssue("E_PATH_GRAPH_FORBIDDEN", f"path={run.path_id.value}"))
    if issues:
        raise DatasetValidationError(issues)


def validate_annotation_bundle(bundle: QuestionAnnotationBundle) -> None:
    issues: list[ValidationIssue] = []
    annotation_ids = [row.annotation_id for row in bundle.evidence_annotations]
    duplicates = _duplicates(annotation_ids)
    if duplicates:
        issues.append(ValidationIssue("E_ANNOTATION_ID_DUPLICATE", ",".join(duplicates)))
    for row in bundle.evidence_annotations:
        if row.question_id != bundle.question_id:
            issues.append(
                ValidationIssue(
                    "E_ANNOTATION_QUESTION_MISMATCH",
                    f"annotation={row.annotation_id}",
                )
            )
        if row.annotation_role != bundle.annotation_role:
            issues.append(
                ValidationIssue(
                    "E_ANNOTATION_ROLE_MISMATCH",
                    f"annotation={row.annotation_id}",
                )
            )
    if issues:
        raise DatasetValidationError(issues)


def validate_manifest(manifest: ExperimentManifest) -> None:
    issues: list[ValidationIssue] = []
    if not manifest.configuration_hashes:
        issues.append(ValidationIssue("E_CONFIG_HASH_MISSING", manifest.experiment_id))
    if not manifest.input_hashes:
        issues.append(ValidationIssue("E_INPUT_HASH_MISSING", manifest.experiment_id))
    if issues:
        raise DatasetValidationError(issues)
