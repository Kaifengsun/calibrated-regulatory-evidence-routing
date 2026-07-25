from __future__ import annotations

from datetime import datetime

import pytest

from evidence_routing.adapters.base import (
    ContextItem,
    CorpusManifest,
    GraphMetadata,
    GraphTarget,
    RegulatoryCorpusAdapter,
    RetrievalCandidate,
    SourceSection,
)
from evidence_routing.authoring import AuthoringRecord, ManualSearchRecord
from evidence_routing.question_validation import (
    find_prior_question_flags,
    normalize_question_text,
    validate_authoring_batch,
)
from evidence_routing.schemas import (
    ConstructionCategory,
    ContextType,
    Domain,
    EvidenceSpecification,
    QueryRecord,
)
from evidence_routing.validation import DatasetValidationError

HASH = "c" * 64


def _section(source_id: str) -> SourceSection:
    return SourceSection(
        domain=Domain.CHEMICAL,
        source_id=source_id,
        document_id=f"DOC-{source_id}",
        heading=f"Heading {source_id}",
        content=f"Attributable content for {source_id}.",
        source_type="section",
        runtime_locator=source_id,
        provenance={"corpus_hash": HASH},
    )


class AuthoringAdapter(RegulatoryCorpusAdapter):
    def __init__(self) -> None:
        self.sections = {
            source_id: _section(source_id)
            for source_id in ("S-D", "S-C", "S-T", "S-G", "TARGET")
        }

    def corpus_manifest(self) -> CorpusManifest:
        return CorpusManifest(Domain.CHEMICAL, HASH, 5, "fixture-v1")

    def bm25_search(self, query: str, limit: int = 50) -> list[RetrievalCandidate]:
        raise AssertionError("authoring validation cannot execute retrieval")

    def get_section(self, source_id: str) -> SourceSection:
        return self.sections[source_id]

    def get_context_sidecars(
        self,
        source_id: str,
        *,
        include_table: bool,
    ) -> list[ContextItem]:
        if source_id == "S-C":
            return [
                ContextItem(
                    "CTX-PARENT",
                    "S-C",
                    "PARENT",
                    "DOC-S-C",
                    ContextType.IMMEDIATE_PARENT,
                    "Material parent context.",
                    {"fixture": "true"},
                )
            ]
        if source_id == "S-T" and include_table:
            return [
                ContextItem(
                    "CTX-TABLE",
                    "S-T",
                    "TABLE",
                    "DOC-S-T",
                    ContextType.TABLE,
                    "Material table content.",
                    {"fixture": "true"},
                )
            ]
        return []

    def get_graph_metadata(self, source_ids: list[str]) -> dict[str, GraphMetadata]:
        return {
            source_id: GraphMetadata(source_id, 0, (), None)
            for source_id in source_ids
        }

    def expand_graph(
        self,
        source_ids: list[str],
        *,
        minimum_confidence: float = 0.85,
    ) -> list[GraphTarget]:
        if "S-G" not in source_ids:
            return []
        return [
            GraphTarget(
                "S-G",
                self.sections["TARGET"],
                "CITES",
                "CITES",
                0.9,
                {"fixture": "true"},
            )
        ]

    def manual_corpus_search(
        self,
        query: str,
        limit: int = 100,
    ) -> list[RetrievalCandidate]:
        raise AssertionError("authoring validation cannot perform manual search")


def _quota() -> dict[tuple[Domain, ConstructionCategory], int]:
    result = {
        (domain, category): 0
        for domain in Domain
        for category in ConstructionCategory
    }
    for category in ConstructionCategory:
        result[(Domain.CHEMICAL, category)] = 1
    return result


def _batch():
    definitions = [
        (ConstructionCategory.DIRECT_CLAUSE, ["S-D"], ["S-D"], False),
        (
            ConstructionCategory.PARENT_HEADING_CONTEXT,
            ["S-C"],
            ["S-C", "PARENT"],
            False,
        ),
        (ConstructionCategory.TABLE_RELATED, ["S-T"], ["S-T", "TABLE"], False),
        (
            ConstructionCategory.CITATION_DEPENDENCY,
            ["S-G"],
            ["S-G", "TARGET"],
            False,
        ),
        (ConstructionCategory.EVIDENCE_INSUFFICIENT, [], [], True),
    ]
    queries = []
    specifications = []
    authoring = []
    for index, (category, anchors, evidence, insufficient) in enumerate(definitions, 1):
        question_id = f"CHEM-AUTHOR-{index:03d}"
        specification_id = f"SPEC-{question_id}"
        queries.append(
            QueryRecord(
                question_id=question_id,
                domain=Domain.CHEMICAL,
                language="zh",
                query_text=f"这是用于验证流程的监管问题 {index}",
                construction_category=category,
                source_group_id=f"GROUP-{index}",
                authoring_source_ids=anchors,
            )
        )
        specifications.append(
            EvidenceSpecification(
                question_id=question_id,
                specification_id=specification_id,
                required_source_ids=evidence,
                insufficiency_candidate=insufficient,
                evidence_scope_note="Fixture evidence scope.",
            )
        )
        authoring.append(
            AuthoringRecord(
                authoring_id=f"AUTHOR-{question_id}",
                question_id=question_id,
                specification_id=specification_id,
                domain=Domain.CHEMICAL,
                construction_category=category,
                construction_rationale="Fixture construction rationale.",
                manual_search_record_id=(
                    f"SEARCH-{question_id}" if insufficient else None
                ),
            )
        )
    searches = [
        ManualSearchRecord(
            manual_search_id="SEARCH-CHEM-AUTHOR-005",
            question_id="CHEM-AUTHOR-005",
            domain=Domain.CHEMICAL,
            checked_by="REVIEWER-A",
            checked_at=datetime.fromisoformat("2026-07-25T12:00:00+08:00"),
            search_scope="Complete frozen fixture corpus.",
            search_methods=["full_text_search"],
            query_terms=["missing evidence"],
            evidence_found=False,
            conclusion="corpus_insufficient",
            rationale="No complete attributable evidence was found.",
        )
    ]
    return queries, specifications, authoring, searches


def test_normalization_ignores_case_punctuation_and_spacing() -> None:
    assert normalize_question_text("What is Required?") == normalize_question_text(
        " what-is required "
    )


def test_prior_question_overlap_is_flagged_deterministically() -> None:
    queries, _, _, _ = _batch()
    flags = find_prior_question_flags(
        [queries[0]],
        {"OLD-2": "unrelated", "OLD-1": queries[0].query_text},
    )
    assert [(row.question_id, row.prior_id, row.normalized_similarity) for row in flags] == [
        ("CHEM-AUTHOR-001", "OLD-1", 1.0)
    ]


def test_valid_path_blind_batch_passes() -> None:
    queries, specifications, authoring, searches = _batch()
    flags = validate_authoring_batch(
        queries,
        specifications,
        authoring,
        searches,
        adapters={Domain.CHEMICAL: AuthoringAdapter()},
        expected_quotas=_quota(),
    )
    assert flags == ()


def test_insufficient_question_requires_manual_negative_search() -> None:
    queries, specifications, authoring, _ = _batch()
    with pytest.raises(DatasetValidationError) as captured:
        validate_authoring_batch(
            queries,
            specifications,
            authoring,
            [],
            adapters={Domain.CHEMICAL: AuthoringAdapter()},
            expected_quotas=_quota(),
        )
    assert "E_MANUAL_SEARCH_REQUIRED" in {
        issue.code for issue in captured.value.issues
    }


def test_exact_prior_question_match_blocks_batch() -> None:
    queries, specifications, authoring, searches = _batch()
    with pytest.raises(DatasetValidationError) as captured:
        validate_authoring_batch(
            queries,
            specifications,
            authoring,
            searches,
            adapters={Domain.CHEMICAL: AuthoringAdapter()},
            prior_questions={"OLD-1": queries[0].query_text},
            expected_quotas=_quota(),
        )
    assert "E_PRIOR_QUESTION_EXACT" in {
        issue.code for issue in captured.value.issues
    }
