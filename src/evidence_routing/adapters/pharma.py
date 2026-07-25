"""Read-only adapter for the frozen pharmaceutical JSON and graph snapshots."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from evidence_routing.adapters.base import (
    ContextItem,
    CorpusManifest,
    GraphMetadata,
    GraphTarget,
    RegulatoryCorpusAdapter,
    RetrievalCandidate,
    SourceSection,
)
from evidence_routing.schemas import ContextType, Domain

_RELATION_MAP = {
    "REFERENCES": "CITES",
    "REQUIRES_COMPLIANCE_WITH": "DEPENDS_ON",
    "APPLIES_DEFINITION_FROM": "DEPENDS_ON",
    "USES_PRINCIPLES_FROM": "DEPENDS_ON",
    "INTERPRETS": "DEPENDS_ON",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise ValueError(f"invalid JSONL at {path.name}:{line_number}") from error
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _aggregate_directory_hash(path: Path) -> str:
    rows = [
        f"{item.name}\t{_sha256(item)}"
        for item in sorted(path.iterdir(), key=lambda item: item.name)
        if item.is_file()
    ]
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(value).casefold())


def _source_text(record: dict[str, Any], max_chars: int = 2000) -> str:
    text = "\n".join(
        str(record.get(key, "")).strip()
        for key in ("parents_context", "heading", "content")
        if str(record.get(key, "")).strip()
    )
    return text[:max_chars]


@dataclass(slots=True)
class _BM25Index:
    identifiers: list[str]
    term_frequencies: list[Counter[str]]
    document_lengths: np.ndarray
    document_frequency: Counter[str]
    average_length: float
    k1: float = 1.2
    b: float = 0.75

    @classmethod
    def build(cls, records: list[dict[str, Any]]) -> _BM25Index:
        identifiers: list[str] = []
        frequencies: list[Counter[str]] = []
        lengths: list[int] = []
        document_frequency: Counter[str] = Counter()
        for row in records:
            tokens = _tokenize(_source_text(row))
            frequency = Counter(tokens)
            identifiers.append(str(row["chunk_id"]))
            frequencies.append(frequency)
            lengths.append(len(tokens))
            document_frequency.update(frequency.keys())
        values = np.asarray(lengths, dtype=np.float64)
        average = float(values.mean()) if len(values) else 0.0
        return cls(
            identifiers,
            frequencies,
            values,
            document_frequency,
            average,
        )

    def search(self, query: str, limit: int) -> list[tuple[str, float]]:
        if self.average_length <= 0.0:
            return []
        query_terms = Counter(_tokenize(query))
        scores = np.zeros(len(self.identifiers), dtype=np.float64)
        count = len(self.identifiers)
        for term, query_weight in query_terms.items():
            frequency_docs = self.document_frequency.get(term, 0)
            if not frequency_docs:
                continue
            inverse_document_frequency = math.log(
                1.0 + (count - frequency_docs + 0.5) / (frequency_docs + 0.5)
            )
            for index, term_frequency in enumerate(self.term_frequencies):
                frequency = term_frequency.get(term, 0)
                if not frequency:
                    continue
                norm = frequency + self.k1 * (
                    1.0 - self.b + self.b * self.document_lengths[index] / self.average_length
                )
                scores[index] += (
                    query_weight * inverse_document_frequency * frequency * (self.k1 + 1.0) / norm
                )
        ranked = sorted(range(count), key=lambda index: (-scores[index], index))
        return [
            (self.identifiers[index], float(scores[index]))
            for index in ranked[:limit]
            if scores[index] > 0.0
        ]


@dataclass(frozen=True, slots=True)
class _NormalizedEdge:
    source_chunk_id: str
    target_chunk_id: str
    original_relation: str
    normalized_relation: str
    source_graph_id: str
    target_graph_id: str


class PharmaceuticalRegulatoryAdapter(RegulatoryCorpusAdapter):
    """Thin adapter that never modifies or copies the source snapshots."""

    def __init__(
        self,
        corpus_path: Path,
        graph_path: Path,
        *,
        source_revision: str,
        expected_record_count: int | None = None,
    ) -> None:
        self.corpus_path = corpus_path.resolve()
        self.graph_path = graph_path.resolve()
        self.source_revision = source_revision
        self._records = self._load_records(expected_record_count)
        self._record_by_id = {str(row["chunk_id"]): row for row in self._records}
        self._document_chunks: dict[str, list[str]] = {}
        for row in self._records:
            self._document_chunks.setdefault(str(row["doc_id"]), []).append(str(row["chunk_id"]))
        self._tables = self._load_tables()
        self._index = _BM25Index.build(self._records)
        self._edges = self._load_normalized_edges()
        self._edges_by_source: dict[str, list[_NormalizedEdge]] = {}
        for edge in self._edges:
            self._edges_by_source.setdefault(edge.source_chunk_id, []).append(edge)
        self._manifest = CorpusManifest(
            domain=Domain.PHARMACEUTICAL,
            corpus_hash=_aggregate_directory_hash(self.corpus_path),
            record_count=len(self._records),
            source_revision=source_revision,
        )

    def _load_records(self, expected_count: int | None) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in sorted(self.corpus_path.glob("*_enriched.json")):
            payload = _read_json(path)
            if not isinstance(payload, list):
                raise ValueError(f"expected a JSON list: {path.name}")
            records.extend(payload)
        identifiers = [str(row.get("chunk_id", "")) for row in records]
        if not records or any(not value for value in identifiers):
            raise ValueError("pharmaceutical corpus has missing chunk_id values")
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("pharmaceutical corpus has duplicate chunk_id values")
        if any(not str(row.get("doc_id", "")) for row in records):
            raise ValueError("pharmaceutical corpus has missing doc_id values")
        if expected_count is not None and len(records) != expected_count:
            raise ValueError(f"expected {expected_count} pharmaceutical chunks, got {len(records)}")
        return records

    def _load_tables(self) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        for path in sorted(self.corpus_path.glob("*_tables.json")):
            for row in _read_json(path):
                chunk_id = str(row.get("chunk_id", ""))
                if chunk_id in self._record_by_id:
                    result.setdefault(chunk_id, []).append(dict(row))
        return result

    def _load_normalized_edges(self) -> list[_NormalizedEdge]:
        nodes_path = self.graph_path / "nodes.jsonl"
        edges_path = self.graph_path / "edges.jsonl"
        if not nodes_path.is_file() or not edges_path.is_file():
            return []
        node_rows = _read_jsonl(nodes_path)
        nodes = {str(row["id"]): row for row in node_rows}
        direct_chunk = {
            graph_id: str(row.get("properties", {}).get("chunk_id", ""))
            for graph_id, row in nodes.items()
            if row.get("label") == "DocChunk"
        }
        document_id = {
            graph_id: str(row.get("properties", {}).get("doc_id", ""))
            for graph_id, row in nodes.items()
            if row.get("label") == "RegulatoryDocument"
        }

        def resolve_target(graph_id: str) -> str | None:
            if graph_id in direct_chunk:
                candidate = direct_chunk[graph_id]
                return candidate if candidate in self._record_by_id else None
            doc_id = document_id.get(graph_id)
            candidates = self._document_chunks.get(doc_id, [])
            return candidates[0] if len(candidates) == 1 else None

        normalized: list[_NormalizedEdge] = []
        for row in _read_jsonl(edges_path):
            original = str(row.get("relation", ""))
            relation = _RELATION_MAP.get(original)
            if relation is None:
                continue
            source_graph_id = str(row.get("source", ""))
            target_graph_id = str(row.get("target", ""))
            target_chunk_id = resolve_target(target_graph_id)
            if target_chunk_id is None:
                continue
            source_ids: list[str] = []
            if source_graph_id in direct_chunk:
                source_ids = [direct_chunk[source_graph_id]]
            else:
                source_doc_id = document_id.get(source_graph_id)
                source_ids = self._document_chunks.get(source_doc_id, [])
            for source_chunk_id in source_ids:
                if source_chunk_id in self._record_by_id and source_chunk_id != target_chunk_id:
                    normalized.append(
                        _NormalizedEdge(
                            source_chunk_id=source_chunk_id,
                            target_chunk_id=target_chunk_id,
                            original_relation=original,
                            normalized_relation=relation,
                            source_graph_id=source_graph_id,
                            target_graph_id=target_graph_id,
                        )
                    )
        return sorted(
            set(normalized),
            key=lambda edge: (
                edge.source_chunk_id,
                edge.normalized_relation,
                edge.target_chunk_id,
                edge.original_relation,
            ),
        )

    def corpus_manifest(self) -> CorpusManifest:
        return self._manifest

    def _section(self, source_id: str) -> SourceSection:
        try:
            row = self._record_by_id[source_id]
        except KeyError as error:
            raise KeyError(f"unknown pharmaceutical source_id: {source_id}") from error
        return SourceSection(
            domain=Domain.PHARMACEUTICAL,
            source_id=source_id,
            document_id=str(row["doc_id"]),
            heading=str(row.get("heading", "")),
            content=str(row.get("content", "")),
            source_type="doc_chunk",
            runtime_locator=source_id,
            provenance={
                "corpus_hash": self._manifest.corpus_hash,
                "source_locator": source_id,
            },
            reranker_text=_source_text(row),
        )

    def bm25_search(self, query: str, limit: int = 50) -> list[RetrievalCandidate]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        return [
            RetrievalCandidate(section=self._section(source_id), rank=rank, score=score)
            for rank, (source_id, score) in enumerate(self._index.search(query, limit), 1)
        ]

    def get_section(self, source_id: str) -> SourceSection:
        return self._section(source_id)

    def get_context_sidecars(self, source_id: str, *, include_table: bool) -> list[ContextItem]:
        row = self._record_by_id.get(source_id)
        if row is None:
            raise KeyError(f"unknown pharmaceutical source_id: {source_id}")
        document_id = str(row["doc_id"])
        items: list[ContextItem] = []
        heading = str(row.get("heading", "")).strip()
        if heading:
            items.append(
                ContextItem(
                    context_id=f"{source_id}:heading",
                    seed_source_id=source_id,
                    source_id=f"{source_id}:heading",
                    document_id=document_id,
                    context_type=ContextType.HEADING_PATH,
                    content=heading,
                    provenance={"source_locator": source_id, "field": "heading"},
                )
            )
        parent = str(row.get("parents_context", "")).strip()
        if parent:
            items.append(
                ContextItem(
                    context_id=f"{source_id}:parent",
                    seed_source_id=source_id,
                    source_id=f"{source_id}:parent",
                    document_id=document_id,
                    context_type=ContextType.IMMEDIATE_PARENT,
                    content=parent,
                    provenance={"source_locator": source_id, "field": "parents_context"},
                )
            )
        if include_table:
            for index, table in enumerate(self._tables.get(source_id, []), 1):
                content = str(table.get("table_summary") or table.get("table") or "").strip()
                if content:
                    items.append(
                        ContextItem(
                            context_id=f"{source_id}:table:{index}",
                            seed_source_id=source_id,
                            source_id=f"{source_id}:table:{index}",
                            document_id=document_id,
                            context_type=ContextType.TABLE,
                            content=content,
                            provenance={
                                "source_locator": source_id,
                                "field": "table_summary" if table.get("table_summary") else "table",
                            },
                        )
                    )
        return items

    def get_graph_metadata(self, source_ids: list[str]) -> dict[str, GraphMetadata]:
        result: dict[str, GraphMetadata] = {}
        for source_id in source_ids:
            if source_id not in self._record_by_id:
                raise KeyError(f"unknown pharmaceutical source_id: {source_id}")
            edges = self._edges_by_source.get(source_id, [])
            result[source_id] = GraphMetadata(
                source_id=source_id,
                eligible_outgoing_count=len({edge.target_chunk_id for edge in edges}),
                relation_types=tuple(sorted({edge.normalized_relation for edge in edges})),
                maximum_confidence=1.0 if edges else None,
            )
        return result

    def expand_graph(
        self, source_ids: list[str], *, minimum_confidence: float = 0.85
    ) -> list[GraphTarget]:
        if minimum_confidence > 1.0:
            return []
        seed_set = set(source_ids)
        result: list[GraphTarget] = []
        seen: set[str] = set()
        for source_id in source_ids:
            if source_id not in self._record_by_id:
                raise KeyError(f"unknown pharmaceutical source_id: {source_id}")
            for edge in self._edges_by_source.get(source_id, []):
                if edge.target_chunk_id in seed_set or edge.target_chunk_id in seen:
                    continue
                seen.add(edge.target_chunk_id)
                result.append(
                    GraphTarget(
                        seed_source_id=source_id,
                        target=self._section(edge.target_chunk_id),
                        relation_type_original=edge.original_relation,
                        relation_type_normalized=edge.normalized_relation,
                        confidence=1.0,
                        provenance={
                            "source_graph_id": edge.source_graph_id,
                            "target_graph_id": edge.target_graph_id,
                            "resolution": "unique_attributable_text_target",
                        },
                    )
                )
        return result

    def manual_corpus_search(self, query: str, limit: int = 100) -> list[RetrievalCandidate]:
        return self.bm25_search(query, limit=limit)
