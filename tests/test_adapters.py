import hashlib
import json
from pathlib import Path

import pytest

from evidence_routing.adapters.base import dataclass_payload
from evidence_routing.adapters.chemical import ChemicalSafetyAdapter
from evidence_routing.adapters.pharma import PharmaceuticalRegulatoryAdapter
from evidence_routing.cache import CacheKey, ResultCache
from evidence_routing.retrieval import run_bm25_once
from evidence_routing.schemas import QueryRecord


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


@pytest.fixture
def pharma_adapter(tmp_path: Path) -> PharmaceuticalRegulatoryAdapter:
    corpus = tmp_path / "corpus"
    graph = tmp_path / "graph"
    _write_json(
        corpus / "demo_enriched.json",
        [
            {
                "chunk_id": "doc_a_C001",
                "doc_id": "doc_a",
                "heading": "Direct requirement",
                "parents_context": "Parent A",
                "content": "The direct safety requirement applies to batches.",
            },
            {
                "chunk_id": "doc_a_C002",
                "doc_id": "doc_a",
                "heading": "Other clause",
                "parents_context": "Parent A",
                "content": "Background material.",
            },
            {
                "chunk_id": "doc_b_C001",
                "doc_id": "doc_b",
                "heading": "Referenced requirement",
                "parents_context": "Parent B",
                "content": "The referenced requirement defines the limit.",
            },
        ],
    )
    _write_json(
        corpus / "demo_tables.json",
        [
            {
                "chunk_id": "doc_a_C001",
                "table": "<table>fixture</table>",
                "table_summary": "Fictional limit table.",
            }
        ],
    )
    nodes = [
        {
            "id": "chunk:doc_a_C001",
            "label": "DocChunk",
            "properties": {"chunk_id": "doc_a_C001", "doc_id": "doc_a"},
        },
        {
            "id": "chunk:doc_a_C002",
            "label": "DocChunk",
            "properties": {"chunk_id": "doc_a_C002", "doc_id": "doc_a"},
        },
        {
            "id": "chunk:doc_b_C001",
            "label": "DocChunk",
            "properties": {"chunk_id": "doc_b_C001", "doc_id": "doc_b"},
        },
        {
            "id": "regdoc:doc_b",
            "label": "RegulatoryDocument",
            "properties": {"doc_id": "doc_b"},
        },
    ]
    edges = [
        {
            "source": "chunk:doc_a_C001",
            "target": "regdoc:doc_b",
            "relation": "REFERENCES",
            "properties": {},
        }
    ]
    _write_jsonl(graph / "nodes.jsonl", nodes)
    _write_jsonl(graph / "edges.jsonl", edges)
    return PharmaceuticalRegulatoryAdapter(
        corpus,
        graph,
        source_revision="fixture-v1",
        expected_record_count=3,
    )


def test_pharma_adapter_contract_and_stable_order(
    pharma_adapter: PharmaceuticalRegulatoryAdapter,
) -> None:
    first = pharma_adapter.bm25_search("direct safety requirement", limit=3)
    second = pharma_adapter.bm25_search("direct safety requirement", limit=3)
    assert first == second
    assert first[0].section.source_id == "doc_a_C001"
    assert first[0].section.provenance["corpus_hash"]
    assert [row.rank for row in first] == list(range(1, len(first) + 1))

    contexts = pharma_adapter.get_context_sidecars("doc_a_C001", include_table=True)
    assert [row.context_type.value for row in contexts] == [
        "heading_path",
        "immediate_parent",
        "table",
    ]

    metadata = pharma_adapter.get_graph_metadata(["doc_a_C001"])
    assert metadata["doc_a_C001"].eligible_outgoing_count == 1
    targets = pharma_adapter.expand_graph(["doc_a_C001"])
    assert len(targets) == 1
    assert targets[0].target.source_id == "doc_b_C001"
    assert targets[0].relation_type_normalized == "CITES"
    assert targets[0].confidence == 1.0


def test_pharma_adapter_does_not_mutate_sources(
    pharma_adapter: PharmaceuticalRegulatoryAdapter,
) -> None:
    files = sorted(
        [
            *pharma_adapter.corpus_path.glob("*"),
            *pharma_adapter.graph_path.glob("*"),
        ]
    )
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    pharma_adapter.bm25_search("requirement")
    pharma_adapter.get_context_sidecars("doc_a_C001", include_table=True)
    pharma_adapter.expand_graph(["doc_a_C001"])
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    assert before == after


class _FakeResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def data(self) -> list[dict]:
        return self._rows


class _FakeSession:
    def __init__(self, queries: list[str]) -> None:
        self.queries = queries

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def run(self, query: str, **_parameters) -> _FakeResult:
        normalized = " ".join(query.split())
        self.queries.append(normalized)
        forbidden = {" CREATE ", " MERGE ", " SET ", " DELETE ", " REMOVE "}
        padded = f" {normalized.upper()} "
        assert not any(token in padded for token in forbidden)
        if "count(section) AS record_count" in query:
            return _FakeResult([{"record_count": 2, "stable_id_count": 2}])
        if "db.index.fulltext.queryNodes" in query:
            return _FakeResult(
                [
                    {
                        "source_id": "chem-sec-1",
                        "runtime_locator": "4:fixture:1",
                        "document_id": "GB-DEMO",
                        "section_number": "1.1",
                        "heading": "Scope",
                        "content": "Fictional chemical requirement.",
                        "score": 9.5,
                    },
                    {
                        "source_id": "chem-sec-2",
                        "runtime_locator": "4:fixture:2",
                        "document_id": "GB-DEMO",
                        "section_number": "2.1",
                        "heading": "Limit",
                        "content": "Fictional limit.",
                        "score": 8.0,
                    },
                ]
            )
        if (
            "MATCH (node:Section {doc_id: $source_id})" in query
            and "parent:" not in query
            and "HAS_TABLE" not in query
        ):
            return _FakeResult(
                [
                    {
                        "source_id": "chem-sec-1",
                        "runtime_locator": "4:fixture:1",
                        "document_id": "GB-DEMO",
                        "section_number": "1.1",
                        "heading": "Scope",
                        "content": "Fictional chemical requirement.",
                    }
                ]
            )
        if "OPTIONAL MATCH (parent:Section)" in query:
            return _FakeResult(
                [
                    {
                        "source_id": "chem-parent-1",
                        "runtime_locator": "4:fixture:p1",
                        "section_number": "1",
                        "heading": "Parent",
                        "content": "Fictional parent.",
                    }
                ]
            )
        if "HAS_TABLE" in query:
            return _FakeResult(
                [
                    {
                        "runtime_locator": "4:fixture:t1",
                        "heading": "Table 1",
                        "content": "Fictional table.",
                    }
                ]
            )
        if "eligible_count" in query:
            return _FakeResult(
                [
                    {
                        "source_id": "chem-sec-1",
                        "eligible_count": 1,
                        "relation_types": ["CITES"],
                        "maximum_confidence": 0.9,
                    }
                ]
            )
        if "seed_rank" in query:
            return _FakeResult(
                [
                    {
                        "seed_source_id": "chem-sec-1",
                        "source_id": "chem-sec-2",
                        "runtime_locator": "4:fixture:2",
                        "document_id": "GB-DEMO",
                        "section_number": "2.1",
                        "heading": "Limit",
                        "content": "Fictional limit.",
                        "relation_type": "CITES",
                        "confidence": 0.9,
                        "seed_rank": 0,
                    }
                ]
            )
        raise AssertionError(f"unexpected query: {normalized}")


class _FakeDriver:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def session(self, **_parameters) -> _FakeSession:
        return _FakeSession(self.queries)


def test_chemical_adapter_contract_is_read_only() -> None:
    driver = _FakeDriver()
    adapter = ChemicalSafetyAdapter(
        driver,
        database="neo4j",
        corpus_hash="a" * 64,
        source_revision="fixture-v1",
    )
    assert adapter.corpus_manifest().record_count == 2
    ranking = adapter.bm25_search("化学品 要求", limit=50)
    assert [row.section.source_id for row in ranking] == [
        "chem-sec-1",
        "chem-sec-2",
    ]
    assert adapter.get_section("chem-sec-1").document_id == "GB-DEMO"
    contexts = adapter.get_context_sidecars("chem-sec-1", include_table=True)
    assert [row.context_type.value for row in contexts] == [
        "heading_path",
        "immediate_parent",
        "table",
    ]
    assert adapter.get_graph_metadata(["chem-sec-1"])["chem-sec-1"].maximum_confidence == 0.9
    assert adapter.expand_graph(["chem-sec-1"])[0].target.source_id == "chem-sec-2"
    assert driver.queries


def test_single_bm25_result_serializes_identically(
    pharma_adapter: PharmaceuticalRegulatoryAdapter,
) -> None:
    query = QueryRecord(
        question_id="PHARMA-PILOT-001",
        domain="pharmaceutical",
        language="en",
        query_text="direct safety requirement",
        construction_category="direct_clause",
        source_group_id="doc_a",
    )
    first = run_bm25_once(pharma_adapter, query)
    second = run_bm25_once(pharma_adapter, query)

    def serialize(value) -> str:
        return json.dumps(dataclass_payload(value), sort_keys=True, separators=(",", ":"))

    assert serialize(first) == serialize(second)


def test_result_cache_is_content_addressed_and_immutable(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path / "cache")
    key = CacheKey(
        domain="chemical",
        corpus_hash="a" * 64,
        query_hash="b" * 64,
        protocol_hash="c" * 64,
        path_id="P0",
        code_commit="d" * 40,
    )
    path = cache.put(key, {"ranking": ["one"]})
    assert cache.get(key) == {"ranking": ["one"]}
    assert cache.put(key, {"ranking": ["one"]}) == path
    with pytest.raises(FileExistsError):
        cache.put(key, {"ranking": ["different"]})
