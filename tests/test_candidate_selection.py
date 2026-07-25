from __future__ import annotations

from evidence_routing.adapters.base import (
    ContextItem,
    CorpusManifest,
    GraphMetadata,
    GraphTarget,
    RegulatoryCorpusAdapter,
    RetrievalCandidate,
    SourceSection,
)
from evidence_routing.candidate_selection import (
    CorpusExpectation,
    inspect_source,
    select_candidate_structures,
)
from evidence_routing.schemas import ConstructionCategory, ContextType, Domain

HASH = "a" * 64


def _section(source_id: str, *, document_id: str = "DOC-1") -> SourceSection:
    return SourceSection(
        domain=Domain.CHEMICAL,
        source_id=source_id,
        document_id=document_id,
        heading=f"Heading {source_id}",
        content=f"Attributable content for {source_id}.",
        source_type="section",
        runtime_locator=f"runtime-{source_id}",
        provenance={"corpus_hash": HASH},
    )


class FixtureAdapter(RegulatoryCorpusAdapter):
    def __init__(self) -> None:
        self.sections = {
            "S1": _section("S1", document_id="DOC-1"),
            "S2": _section("S2", document_id="DOC-2"),
            "S3": _section("S3", document_id="DOC-3"),
            "TARGET": _section("TARGET", document_id="DOC-T"),
        }
        self.search_calls = 0

    def corpus_manifest(self) -> CorpusManifest:
        return CorpusManifest(
            domain=Domain.CHEMICAL,
            corpus_hash=HASH,
            record_count=4,
            source_revision="fixture-v1",
        )

    def bm25_search(self, query: str, limit: int = 50) -> list[RetrievalCandidate]:
        self.search_calls += 1
        raise AssertionError("candidate selection must not run retrieval paths")

    def get_section(self, source_id: str) -> SourceSection:
        return self.sections[source_id]

    def get_context_sidecars(
        self,
        source_id: str,
        *,
        include_table: bool,
    ) -> list[ContextItem]:
        if source_id == "S1":
            return [
                ContextItem(
                    context_id="CTX-PARENT",
                    seed_source_id="S1",
                    source_id="PARENT",
                    document_id="DOC-1",
                    context_type=ContextType.IMMEDIATE_PARENT,
                    content="Material parent scope.",
                    provenance={"source": "fixture"},
                )
            ]
        if source_id == "S2" and include_table:
            return [
                ContextItem(
                    context_id="CTX-TABLE",
                    seed_source_id="S2",
                    source_id="TABLE-1",
                    document_id="DOC-2",
                    context_type=ContextType.TABLE,
                    content="Attributable table value.",
                    provenance={"source": "fixture"},
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
        if "S3" not in source_ids:
            return []
        return [
            GraphTarget(
                seed_source_id="S3",
                target=self.sections["TARGET"],
                relation_type_original="CITES",
                relation_type_normalized="CITES",
                confidence=0.9,
                provenance={"source": "fixture"},
            )
        ]

    def manual_corpus_search(
        self,
        query: str,
        limit: int = 100,
    ) -> list[RetrievalCandidate]:
        self.search_calls += 1
        raise AssertionError("candidate selection must not perform manual searches")


def _expectation() -> CorpusExpectation:
    return CorpusExpectation(
        domain=Domain.CHEMICAL,
        corpus_hash=HASH,
        record_count=4,
        source_revision="fixture-v1",
    )


def test_inspect_source_emits_only_available_structures() -> None:
    adapter = FixtureAdapter()
    categories = {
        row.proposed_category for row in inspect_source(adapter, "S1")
    }
    assert categories == {
        ConstructionCategory.DIRECT_CLAUSE,
        ConstructionCategory.PARENT_HEADING_CONTEXT,
    }
    assert adapter.search_calls == 0


def test_selection_is_path_blind_balanced_and_deterministic() -> None:
    adapter = FixtureAdapter()
    first = select_candidate_structures(
        adapter,
        ["S3", "S2", "S1", "S1"],
        expected_corpus=_expectation(),
        limits={
            ConstructionCategory.DIRECT_CLAUSE: 1,
            ConstructionCategory.PARENT_HEADING_CONTEXT: 1,
            ConstructionCategory.TABLE_RELATED: 1,
            ConstructionCategory.CITATION_DEPENDENCY: 1,
        },
    )
    second = select_candidate_structures(
        adapter,
        ["S1", "S2", "S3"],
        expected_corpus=_expectation(),
        limits={
            ConstructionCategory.DIRECT_CLAUSE: 1,
            ConstructionCategory.PARENT_HEADING_CONTEXT: 1,
            ConstructionCategory.TABLE_RELATED: 1,
            ConstructionCategory.CITATION_DEPENDENCY: 1,
        },
    )
    assert first == second
    assert [row.proposed_category for row in first] == [
        ConstructionCategory.DIRECT_CLAUSE,
        ConstructionCategory.PARENT_HEADING_CONTEXT,
        ConstructionCategory.TABLE_RELATED,
        ConstructionCategory.CITATION_DEPENDENCY,
    ]
    assert adapter.search_calls == 0


def test_selection_rejects_manifest_mismatch() -> None:
    adapter = FixtureAdapter()
    wrong = CorpusExpectation(
        domain=Domain.CHEMICAL,
        corpus_hash="b" * 64,
        record_count=4,
        source_revision="fixture-v1",
    )
    try:
        select_candidate_structures(adapter, ["S1"], expected_corpus=wrong)
    except ValueError as error:
        assert "corpus_hash" in str(error)
    else:
        raise AssertionError("manifest mismatch should fail")


def test_selection_propagates_unknown_source_identity() -> None:
    adapter = FixtureAdapter()
    try:
        select_candidate_structures(
            adapter,
            ["UNKNOWN"],
            expected_corpus=_expectation(),
        )
    except KeyError as error:
        assert "UNKNOWN" in str(error)
    else:
        raise AssertionError("unknown source identity should fail")


def test_graph_confidence_threshold_is_enforced() -> None:
    adapter = FixtureAdapter()
    original = adapter.expand_graph

    def low_confidence(source_ids, *, minimum_confidence=0.85):
        rows = original(source_ids, minimum_confidence=minimum_confidence)
        return [
            GraphTarget(
                seed_source_id=row.seed_source_id,
                target=row.target,
                relation_type_original=row.relation_type_original,
                relation_type_normalized=row.relation_type_normalized,
                confidence=0.84,
                provenance=row.provenance,
            )
            for row in rows
        ]

    adapter.expand_graph = low_confidence
    try:
        inspect_source(adapter, "S3")
    except ValueError as error:
        assert "confidence" in str(error)
    else:
        raise AssertionError("low-confidence graph target should fail")
