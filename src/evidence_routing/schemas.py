"""Strict, versioned data contracts for the evidence-routing Pilot."""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    model_validator,
)

SCHEMA_VERSION = "1.0"
IDENTIFIER_PATTERN = r"^[^\x00-\x1f\x7f]{1,128}$"
Identifier = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=IDENTIFIER_PATTERN,
    ),
]


class StrictModel(BaseModel):
    """Base contract shared by all public records."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    schema_version: Literal["1.0"] = SCHEMA_VERSION


class Domain(StrEnum):
    CHEMICAL = "chemical"
    PHARMACEUTICAL = "pharmaceutical"


class ConstructionCategory(StrEnum):
    DIRECT_CLAUSE = "direct_clause"
    PARENT_HEADING_CONTEXT = "parent_heading_context"
    TABLE_RELATED = "table_related"
    CITATION_DEPENDENCY = "citation_dependency"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"


class PathId(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"


class EvidenceLabel(StrEnum):
    REQUIRED = "REQUIRED"
    SUFFICIENT = "SUFFICIENT"
    CONTEXT = "CONTEXT"
    IRRELEVANT = "IRRELEVANT"
    HARMFUL = "HARMFUL"


class ContextType(StrEnum):
    HEADING_PATH = "heading_path"
    IMMEDIATE_PARENT = "immediate_parent"
    TABLE = "table"


class UnitOrigin(StrEnum):
    DIRECT = "direct"
    GRAPH = "graph"


class AnnotationRole(StrEnum):
    PRIMARY = "primary"
    DUPLICATE = "duplicate"
    ADJUDICATED = "adjudicated"


class ExecutionStatus(StrEnum):
    COMPLETE = "complete"
    EXECUTION_ERROR = "execution_error"


class CorpusAssessment(StrEnum):
    UNCHECKED = "unchecked"
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


class QueryRecord(StrictModel):
    question_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    domain: Domain
    language: Literal["zh", "en"]
    query_text: str = Field(min_length=3, max_length=1000)
    construction_category: ConstructionCategory
    source_group_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    authoring_source_ids: list[Identifier] = Field(default_factory=list, max_length=20)
    counter_cue_tags: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def language_matches_domain(self) -> QueryRecord:
        expected = "zh" if self.domain == Domain.CHEMICAL else "en"
        if self.language != expected:
            raise ValueError(f"language must be {expected!r} for domain {self.domain.value!r}")
        return self


class EvidenceSpecification(StrictModel):
    question_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    specification_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    required_source_ids: list[Identifier] = Field(default_factory=list, max_length=20)
    sufficient_source_ids: list[Identifier] = Field(default_factory=list, max_length=20)
    insufficiency_candidate: bool = False
    evidence_scope_note: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def valid_satisfaction_contract(self) -> EvidenceSpecification:
        required = set(self.required_source_ids)
        sufficient = set(self.sufficient_source_ids)
        if len(required) != len(self.required_source_ids):
            raise ValueError("required_source_ids must be unique")
        if len(sufficient) != len(self.sufficient_source_ids):
            raise ValueError("sufficient_source_ids must be unique")
        if required & sufficient:
            raise ValueError("an identifier cannot be both REQUIRED and SUFFICIENT")
        if not required and not sufficient and not self.insufficiency_candidate:
            raise ValueError("at least one evidence identifier is required")
        if self.insufficiency_candidate and (required or sufficient):
            raise ValueError("insufficiency candidates cannot predeclare corpus evidence IDs")
        return self


class RankedEvidenceUnit(StrictModel):
    source_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    document_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    domain: Domain
    source_type: str = Field(min_length=1, max_length=40)
    rank: PositiveInt = Field(le=10)
    origin: UnitOrigin
    bm25_rank: PositiveInt = Field(le=50)
    bm25_score: float
    reranker_score: float | None = Field(default=None, ge=0.0, le=1.0)
    graph_seed_source_id: Identifier | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    relation_type_original: str | None = Field(default=None, max_length=80)
    relation_type_normalized: Literal["CITES", "DEPENDS_ON"] | None = None
    relation_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    provenance: dict[str, str] = Field(min_length=1)

    @model_validator(mode="after")
    def graph_fields_match_origin(self) -> RankedEvidenceUnit:
        graph_fields = (
            self.graph_seed_source_id,
            self.relation_type_original,
            self.relation_type_normalized,
            self.relation_confidence,
        )
        if self.origin == UnitOrigin.GRAPH and any(value is None for value in graph_fields):
            raise ValueError("graph units require complete relation provenance")
        if self.origin == UnitOrigin.DIRECT and any(value is not None for value in graph_fields):
            raise ValueError("direct units cannot contain graph relation fields")
        return self


class ContextSidecar(StrictModel):
    sidecar_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    seed_source_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    seed_rank: PositiveInt = Field(le=5)
    source_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    document_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    domain: Domain
    context_type: ContextType
    order_within_seed: PositiveInt = Field(le=3)
    provenance: dict[str, str] = Field(min_length=1)


class PathRun(StrictModel):
    run_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    question_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    path_id: PathId
    status: ExecutionStatus
    ranked_units: list[RankedEvidenceUnit] = Field(default_factory=list, max_length=10)
    context_sidecars: list[ContextSidecar] = Field(default_factory=list, max_length=15)
    error_code: str | None = Field(default=None, max_length=80)
    neural_model_calls: NonNegativeInt
    graph_targets_inserted: NonNegativeInt = Field(le=5)
    context_items_attached: NonNegativeInt = Field(le=15)
    runtime_ms: NonNegativeInt

    @model_validator(mode="after")
    def status_contract(self) -> PathRun:
        if self.status == ExecutionStatus.COMPLETE and self.error_code is not None:
            raise ValueError("complete path runs cannot contain error_code")
        if self.status == ExecutionStatus.EXECUTION_ERROR and not self.error_code:
            raise ValueError("execution errors require error_code")
        if self.context_items_attached != len(self.context_sidecars):
            raise ValueError("context_items_attached must equal sidecar count")
        if self.graph_targets_inserted != sum(
            unit.origin == UnitOrigin.GRAPH for unit in self.ranked_units
        ):
            raise ValueError("graph_targets_inserted must equal graph-unit count")
        return self


class EvidenceAnnotation(StrictModel):
    annotation_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    question_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    path_id: PathId
    evidence_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    evidence_kind: Literal["ranked", "sidecar"]
    label: EvidenceLabel
    annotation_role: AnnotationRole
    annotator_code: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    annotated_at: datetime
    harmful_reason_code: (
        Literal[
            "wrong_version",
            "wrong_regulated_object",
            "wrong_scope_condition_or_exception",
            "direct_conflict",
            "materially_misleading",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def harmful_reason_matches_label(self) -> EvidenceAnnotation:
        if self.label == EvidenceLabel.HARMFUL and self.harmful_reason_code is None:
            raise ValueError("HARMFUL labels require harmful_reason_code")
        if self.label != EvidenceLabel.HARMFUL and self.harmful_reason_code is not None:
            raise ValueError("harmful_reason_code is allowed only for HARMFUL labels")
        if self.annotated_at.utcoffset() is None:
            raise ValueError("annotated_at must include a timezone")
        return self


class ManualCorpusCheck(StrictModel):
    checked: bool
    checked_by: Identifier | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    checked_at: datetime | None = None
    search_scope: str | None = Field(default=None, max_length=1000)
    evidence_found: bool | None = None

    @model_validator(mode="after")
    def complete_when_checked(self) -> ManualCorpusCheck:
        details = (self.checked_by, self.checked_at, self.search_scope, self.evidence_found)
        if self.checked and any(value is None for value in details):
            raise ValueError("checked manual searches require all check details")
        if not self.checked and any(value is not None for value in details):
            raise ValueError("unchecked manual searches cannot contain check details")
        if self.checked_at is not None and self.checked_at.utcoffset() is None:
            raise ValueError("checked_at must include a timezone")
        return self


class QuestionAnnotationBundle(StrictModel):
    bundle_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    question_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    annotation_role: AnnotationRole
    path_run_ids: list[Identifier] = Field(min_length=6, max_length=6)
    evidence_annotations: list[EvidenceAnnotation]
    corpus_assessment: CorpusAssessment = CorpusAssessment.UNCHECKED
    manual_corpus_check: ManualCorpusCheck = Field(
        default_factory=lambda: ManualCorpusCheck(checked=False)
    )

    @model_validator(mode="after")
    def corpus_insufficiency_is_manually_supported(self) -> QuestionAnnotationBundle:
        if len(set(self.path_run_ids)) != 6:
            raise ValueError("path_run_ids must contain six unique runs")
        if self.corpus_assessment == CorpusAssessment.INSUFFICIENT:
            check = self.manual_corpus_check
            if not check.checked or check.evidence_found is not False:
                raise ValueError(
                    "corpus insufficiency requires a completed manual check finding no evidence"
                )
        return self


class AdjudicationRecord(StrictModel):
    adjudication_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    question_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    path_id: PathId
    evidence_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    primary_annotation_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    duplicate_annotation_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    primary_label: EvidenceLabel
    duplicate_label: EvidenceLabel
    adjudicated_label: EvidenceLabel
    adjudicator_code: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    rationale_code: str = Field(min_length=1, max_length=80)
    adjudicated_at: datetime

    @model_validator(mode="after")
    def timezone_required(self) -> AdjudicationRecord:
        if self.adjudicated_at.utcoffset() is None:
            raise ValueError("adjudicated_at must include a timezone")
        return self


class SplitAssignment(StrictModel):
    question_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    source_group_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    domain: Domain
    fold: int = Field(ge=0, le=4)
    assignment_seed: int = 20260723
    assignment_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ExperimentManifest(StrictModel):
    experiment_id: Identifier = Field(pattern=IDENTIFIER_PATTERN)
    created_at: datetime
    code_commit: str = Field(pattern=r"^[a-f0-9]{40}$")
    protocol_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    configuration_hashes: dict[str, str]
    corpus_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    model_id: str | None = Field(default=None, max_length=200)
    model_revision: str | None = Field(default=None, max_length=200)
    seed: int
    command: str = Field(min_length=1, max_length=1000)
    input_hashes: dict[str, str] = Field(default_factory=dict)
    output_hashes: dict[str, str] = Field(default_factory=dict)
    runtime_environment: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_manifest(self) -> ExperimentManifest:
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        hash_maps = (
            self.configuration_hashes,
            self.input_hashes,
            self.output_hashes,
        )
        if any(
            not value or len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
            for mapping in hash_maps
            for value in mapping.values()
        ):
            raise ValueError("all recorded hashes must be lowercase SHA-256 values")
        return self


SCHEMA_MODELS: dict[str, type[StrictModel]] = {
    "query-record": QueryRecord,
    "evidence-specification": EvidenceSpecification,
    "ranked-evidence-unit": RankedEvidenceUnit,
    "context-sidecar": ContextSidecar,
    "path-run": PathRun,
    "evidence-annotation": EvidenceAnnotation,
    "question-annotation-bundle": QuestionAnnotationBundle,
    "adjudication-record": AdjudicationRecord,
    "split-assignment": SplitAssignment,
    "experiment-manifest": ExperimentManifest,
}


def export_json_schemas(destination: Path) -> list[Path]:
    """Write deterministic JSON Schemas for every public contract."""
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in sorted(SCHEMA_MODELS.items()):
        path = destination / f"{name}-v1.schema.json"
        payload: dict[str, Any] = model.model_json_schema()
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written
