from evidence_routing.adapters.base import (
    ContextItem,
    GraphTarget,
    RetrievalCandidate,
    SourceSection,
)
from evidence_routing.context import attach_context
from evidence_routing.graph import expand_one_hop
from evidence_routing.reranking import direct_candidates
from evidence_routing.schemas import ContextType, Domain


def _section(source_id: str) -> SourceSection:
    return SourceSection(
        domain=Domain.CHEMICAL,
        source_id=source_id,
        document_id="STD-DEMO",
        heading=f"Heading {source_id}",
        content="Fictional evidence.",
        source_type="section",
        runtime_locator=f"runtime:{source_id}",
        provenance={"locator": f"fixture:{source_id}"},
    )


def _candidates(count: int = 10):
    return [
        RetrievalCandidate(section=_section(f"S{index:02d}"), rank=index, score=20 - index)
        for index in range(1, count + 1)
    ]


class _StageAdapter:
    def get_context_sidecars(self, source_id: str, *, include_table: bool):
        assert include_table is True
        return [
            ContextItem(
                context_id=f"{source_id}:table",
                seed_source_id=source_id,
                source_id=f"{source_id}:table",
                document_id="STD-DEMO",
                context_type=ContextType.TABLE,
                content="Fictional table.",
                provenance={"kind": "table"},
            ),
            ContextItem(
                context_id=f"{source_id}:parent",
                seed_source_id=source_id,
                source_id=f"{source_id}:parent",
                document_id="STD-DEMO",
                context_type=ContextType.IMMEDIATE_PARENT,
                content="Fictional parent.",
                provenance={"kind": "parent"},
            ),
            ContextItem(
                context_id=f"{source_id}:heading",
                seed_source_id=source_id,
                source_id=f"{source_id}:heading",
                document_id="STD-DEMO",
                context_type=ContextType.HEADING_PATH,
                content="Fictional heading.",
                provenance={"kind": "heading"},
            ),
            ContextItem(
                context_id=f"{source_id}:table-extra",
                seed_source_id=source_id,
                source_id=f"{source_id}:table-extra",
                document_id="STD-DEMO",
                context_type=ContextType.TABLE,
                content="Extra fictional table.",
                provenance={"kind": "table"},
            ),
        ]

    def expand_graph(self, source_ids, *, minimum_confidence=0.85):
        assert source_ids == ["S01", "S02", "S03", "S04", "S05"]
        assert minimum_confidence == 0.85
        return [
            GraphTarget(
                seed_source_id="S02",
                target=_section("G02"),
                relation_type_original="DEPENDS_ON",
                relation_type_normalized="DEPENDS_ON",
                confidence=0.95,
                provenance={"edge": "two"},
            ),
            GraphTarget(
                seed_source_id="S01",
                target=_section("G01"),
                relation_type_original="CITES",
                relation_type_normalized="CITES",
                confidence=0.90,
                provenance={"edge": "one"},
            ),
            GraphTarget(
                seed_source_id="S01",
                target=_section("S08"),
                relation_type_original="CITES",
                relation_type_normalized="CITES",
                confidence=0.99,
                provenance={"edge": "duplicate-direct"},
            ),
            GraphTarget(
                seed_source_id="S01",
                target=_section("G00"),
                relation_type_original="CITES",
                relation_type_normalized="CITES",
                confidence=0.80,
                provenance={"edge": "below-threshold"},
            ),
        ]


def test_context_is_ordered_bounded_and_limited_to_five_seeds() -> None:
    rows = direct_candidates(_candidates(10))
    attached = attach_context(_StageAdapter(), rows, query_text="fictional table question")
    assert len(attached) == 15
    assert {row.seed_rank for row in attached} == {1, 2, 3, 4, 5}
    first = [row.item.context_type for row in attached if row.seed_rank == 1]
    assert first == [
        ContextType.HEADING_PATH,
        ContextType.IMMEDIATE_PARENT,
        ContextType.TABLE,
    ]


def test_graph_preserves_seeds_orders_targets_and_fills_direct_remainder() -> None:
    rows = direct_candidates(_candidates(10))
    expanded = expand_one_hop(_StageAdapter(), rows)
    identifiers = [
        row.direct.candidate.section.source_id
        if row.direct is not None
        else row.graph.target.source_id
        for row in expanded
    ]
    assert identifiers == [
        "S01",
        "S02",
        "S03",
        "S04",
        "S05",
        "G01",
        "G02",
        "S06",
        "S07",
        "S08",
    ]
    assert sum(row.graph is not None for row in expanded) == 2
