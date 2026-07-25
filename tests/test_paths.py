from evidence_routing.adapters.base import (
    ContextItem,
    CorpusManifest,
    GraphTarget,
    RetrievalCandidate,
    SourceSection,
)
from evidence_routing.paths import run_p0, run_p1, run_p2, run_p3, run_p4, run_p5
from evidence_routing.reranking import rank_with_scores
from evidence_routing.retrieval import FirstStageResult
from evidence_routing.schemas import ContextType, Domain, PathId, UnitOrigin


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
        reranker_text=f"Heading {source_id}\nFictional evidence.",
    )


def _first_stage() -> FirstStageResult:
    candidates = tuple(
        RetrievalCandidate(
            section=_section(f"S{index:02d}"),
            rank=index,
            score=float(100 - index),
        )
        for index in range(1, 11)
    )
    return FirstStageResult(
        question_id="CHEM-PILOT-DEMO",
        query="fictional requirement",
        manifest=CorpusManifest(
            domain=Domain.CHEMICAL,
            corpus_hash="a" * 64,
            record_count=10,
            source_revision="fixture-v1",
        ),
        candidates=candidates,
    )


class _ReverseReranker:
    def rerank(self, query, candidates):
        assert query == "fictional requirement"
        return rank_with_scores(candidates, [index / 10 for index in range(1, 11)])


class _PathAdapter:
    def __init__(self):
        self.context_seeds = []
        self.graph_seeds = []

    def get_context_sidecars(self, source_id, *, include_table):
        self.context_seeds.append(source_id)
        return [
            ContextItem(
                context_id=f"{source_id}:heading",
                seed_source_id=source_id,
                source_id=f"{source_id}:heading",
                document_id="STD-DEMO",
                context_type=ContextType.HEADING_PATH,
                content="Fictional heading.",
                provenance={"kind": "heading"},
            )
        ]

    def expand_graph(self, source_ids, *, minimum_confidence=0.85):
        self.graph_seeds.append(tuple(source_ids))
        return [
            GraphTarget(
                seed_source_id=source_ids[0],
                target=_section("G01"),
                relation_type_original="CITES",
                relation_type_normalized="CITES",
                confidence=0.9,
                provenance={"edge": "fixture"},
            )
        ]


def test_all_six_path_compositions_are_schema_valid() -> None:
    first = _first_stage()
    reranker = _ReverseReranker()
    adapter = _PathAdapter()
    runs = [
        run_p0(first),
        run_p1(first, reranker),
        run_p2(first, adapter),
        run_p3(first, adapter),
        run_p4(first, adapter, reranker),
        run_p5(first, adapter, reranker),
    ]
    assert [run.path_id for run in runs] == list(PathId)
    assert all([unit.rank for unit in run.ranked_units] == list(range(1, 11)) for run in runs)
    assert runs[0].neural_model_calls == 0
    assert runs[1].ranked_units[0].source_id == "S10"
    assert len(runs[2].context_sidecars) == 5
    assert runs[3].ranked_units[5].origin == UnitOrigin.GRAPH
    assert runs[4].context_sidecars[0].seed_source_id == "S10"
    assert runs[5].graph_targets_inserted == 1
    assert all("content" not in unit.model_dump() for run in runs for unit in run.ranked_units)


def test_p5_freezes_the_same_five_context_and_graph_seeds() -> None:
    adapter = _PathAdapter()
    run_p5(_first_stage(), adapter, _ReverseReranker())
    assert adapter.context_seeds[-5:] == ["S10", "S09", "S08", "S07", "S06"]
    assert adapter.graph_seeds[-1] == ("S10", "S09", "S08", "S07", "S06")
