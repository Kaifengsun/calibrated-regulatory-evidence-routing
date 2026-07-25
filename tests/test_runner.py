from evidence_routing.adapters.base import (
    ContextItem,
    CorpusManifest,
    GraphTarget,
    RetrievalCandidate,
    SourceSection,
)
from evidence_routing.reranking import rank_with_scores
from evidence_routing.runner import run_all_paths
from evidence_routing.schemas import (
    ConstructionCategory,
    ContextType,
    Domain,
    ExecutionStatus,
    PathId,
    QueryRecord,
)


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


class _CountingAdapter:
    def __init__(self, *, fail_bm25=False):
        self.bm25_calls = 0
        self.fail_bm25 = fail_bm25

    def corpus_manifest(self):
        return CorpusManifest(
            domain=Domain.CHEMICAL,
            corpus_hash="a" * 64,
            record_count=10,
            source_revision="fixture-v1",
        )

    def bm25_search(self, query, limit=50):
        self.bm25_calls += 1
        if self.fail_bm25:
            raise RuntimeError("fixture first-stage failure")
        return [
            RetrievalCandidate(_section(f"S{index:02d}"), index, float(100 - index))
            for index in range(1, 11)
        ]

    def get_context_sidecars(self, source_id, *, include_table):
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


class _SelectiveFailureReranker:
    def __init__(self):
        self.calls = 0

    def rerank(self, query, candidates):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("fixture P4 failure")
        return rank_with_scores(candidates, [index / 10 for index in range(1, 11)])


def _query() -> QueryRecord:
    return QueryRecord(
        question_id="CHEM-PILOT-DEMO",
        domain=Domain.CHEMICAL,
        language="zh",
        query_text="fictional chemical requirement",
        construction_category=ConstructionCategory.DIRECT_CLAUSE,
        source_group_id="STD-DEMO",
    )


def test_runner_reuses_bm25_and_isolates_downstream_failure() -> None:
    adapter = _CountingAdapter()
    reranker = _SelectiveFailureReranker()
    runs = run_all_paths(adapter, _query(), reranker)
    assert adapter.bm25_calls == 1
    assert [run.path_id for run in runs] == list(PathId)
    assert runs[4].status == ExecutionStatus.EXECUTION_ERROR
    assert runs[4].error_code == "E_P4_EXECUTION"
    assert all(
        run.status == ExecutionStatus.COMPLETE
        for index, run in enumerate(runs)
        if index != 4
    )


def test_runner_records_all_paths_when_first_stage_fails() -> None:
    adapter = _CountingAdapter(fail_bm25=True)
    runs = run_all_paths(adapter, _query(), _SelectiveFailureReranker())
    assert adapter.bm25_calls == 1
    assert len(runs) == 6
    assert all(run.status == ExecutionStatus.EXECUTION_ERROR for run in runs)
    assert {run.error_code for run in runs} == {"E_FIRST_STAGE"}
