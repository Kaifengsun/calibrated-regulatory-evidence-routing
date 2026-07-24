"""Read-only Neo4j adapter for the frozen chemical-safety graph."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any, Protocol

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


class _Result(Protocol):
    def data(self) -> list[dict[str, Any]]: ...


class _Session(Protocol):
    def run(self, query: str, **parameters: Any) -> _Result: ...


class _Driver(Protocol):
    def session(self, **parameters: Any) -> AbstractContextManager[_Session]: ...


def _lucene_query(text: str) -> str:
    cleaned = re.sub(r'[+\-!(){}\[\]^"~*?:\\/]|&&|\|\|', " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def _derived_id(prefix: str, *values: str) -> str:
    digest = hashlib.sha256("\0".join(values).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


class ChemicalSafetyAdapter(RegulatoryCorpusAdapter):
    """Thin adapter over one externally managed, read-only Neo4j snapshot."""

    def __init__(
        self,
        driver: _Driver,
        *,
        database: str | None,
        corpus_hash: str,
        source_revision: str,
    ) -> None:
        if not re.fullmatch(r"[a-f0-9]{64}", corpus_hash):
            raise ValueError("chemical corpus_hash must be a lowercase SHA-256")
        self._driver = driver
        self.database = database
        self._corpus_hash = corpus_hash
        self.source_revision = source_revision
        self._manifest: CorpusManifest | None = None

    @classmethod
    def connect(
        cls,
        *,
        uri: str,
        user: str,
        password: str,
        database: str | None,
        corpus_hash: str,
        source_revision: str,
        driver_factory: Callable[..., _Driver] | None = None,
    ) -> ChemicalSafetyAdapter:
        """Create a driver without logging or storing connection credentials."""
        if driver_factory is None:
            try:
                from neo4j import GraphDatabase
            except ImportError as error:
                raise RuntimeError(
                    "install the project runtime dependencies to use Neo4j"
                ) from error
            driver_factory = GraphDatabase.driver
        driver = driver_factory(uri, auth=(user, password))
        return cls(
            driver,
            database=database,
            corpus_hash=corpus_hash,
            source_revision=source_revision,
        )

    def _session_parameters(self) -> dict[str, str]:
        return {} if self.database is None else {"database": self.database}

    def corpus_manifest(self) -> CorpusManifest:
        if self._manifest is None:
            with self._driver.session(**self._session_parameters()) as session:
                rows = session.run(
                    """
                    MATCH (section:Section)
                    RETURN count(section) AS record_count,
                           count(section.uid) AS stable_id_present,
                           count(DISTINCT section.uid) AS stable_id_count
                    """
                ).data()
            if len(rows) != 1:
                raise RuntimeError("chemical corpus count query returned no unique result")
            count = int(rows[0]["record_count"])
            stable_present = int(rows[0]["stable_id_present"])
            stable_count = int(rows[0]["stable_id_count"])
            if count <= 0 or stable_present != count or stable_count != count:
                raise RuntimeError(
                    "chemical Section.uid values must be present and globally unique"
                )
            self._manifest = CorpusManifest(
                domain=Domain.CHEMICAL,
                corpus_hash=self._corpus_hash,
                record_count=count,
                source_revision=self.source_revision,
            )
        return self._manifest

    def _section_from_row(self, row: dict[str, Any]) -> SourceSection:
        source_id = str(row.get("source_id") or "")
        runtime_locator = str(row.get("runtime_locator") or "")
        if not source_id or not runtime_locator:
            raise RuntimeError("chemical result lacks stable or runtime identity")
        return SourceSection(
            domain=Domain.CHEMICAL,
            source_id=source_id,
            document_id=str(row.get("document_id") or source_id),
            heading=" ".join(
                value
                for value in (
                    str(row.get("section_number") or "").strip(),
                    str(row.get("heading") or "").strip(),
                )
                if value
            ),
            content=str(row.get("content") or ""),
            source_type="section",
            runtime_locator=runtime_locator,
            provenance={
                "corpus_hash": self._corpus_hash,
                "runtime_locator": runtime_locator,
            },
        )

    def bm25_search(self, query: str, limit: int = 50) -> list[RetrievalCandidate]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        text_query = _lucene_query(query)
        if not text_query:
            return []
        with self._driver.session(**self._session_parameters()) as session:
            rows = session.run(
                """
                CALL db.index.fulltext.queryNodes(
                    'section_fulltext_cjk', $text_query, {limit: $limit}
                )
                YIELD node, score
                OPTIONAL MATCH (standard:Standard {uid: node.standard_uid})
                RETURN node.uid AS source_id,
                       elementId(node) AS runtime_locator,
                       coalesce(
                           standard.standard_id, standard.uid,
                           node.standard_uid, node.raw_standard_id, node.doc_id
                       ) AS document_id,
                       node.section_number AS section_number,
                       node.title AS heading,
                       node.content AS content,
                       score
                ORDER BY score DESC, source_id ASC
                """,
                text_query=text_query,
                limit=limit,
            ).data()
        result: list[RetrievalCandidate] = []
        seen: dict[str, str] = {}
        for row in rows:
            section = self._section_from_row(row)
            previous = seen.get(section.source_id)
            if previous is not None and previous != section.runtime_locator:
                raise RuntimeError(f"duplicate chemical Section.uid: {section.source_id}")
            if previous is not None:
                continue
            seen[section.source_id] = section.runtime_locator
            result.append(
                RetrievalCandidate(
                    section=section,
                    rank=len(result) + 1,
                    score=float(row["score"]),
                )
            )
        return result

    def get_section(self, source_id: str) -> SourceSection:
        with self._driver.session(**self._session_parameters()) as session:
            rows = session.run(
                """
                MATCH (node:Section {uid: $source_id})
                OPTIONAL MATCH (standard:Standard {uid: node.standard_uid})
                RETURN node.uid AS source_id,
                       elementId(node) AS runtime_locator,
                       coalesce(
                           standard.standard_id, standard.uid,
                           node.standard_uid, node.raw_standard_id, node.doc_id
                       ) AS document_id,
                       node.section_number AS section_number,
                       node.title AS heading,
                       node.content AS content
                """,
                source_id=source_id,
            ).data()
        if len(rows) != 1:
            raise KeyError(f"expected one chemical Section for {source_id!r}, got {len(rows)}")
        return self._section_from_row(rows[0])

    def get_context_sidecars(self, source_id: str, *, include_table: bool) -> list[ContextItem]:
        seed = self.get_section(source_id)
        items: list[ContextItem] = []
        if seed.heading:
            items.append(
                ContextItem(
                    context_id=f"{source_id}:heading",
                    seed_source_id=source_id,
                    source_id=f"{source_id}:heading",
                    document_id=seed.document_id,
                    context_type=ContextType.HEADING_PATH,
                    content=f"{seed.document_id} {seed.heading}".strip(),
                    provenance={
                        "runtime_locator": seed.runtime_locator,
                        "field": "section_number+title",
                    },
                )
            )
        with self._driver.session(**self._session_parameters()) as session:
            parent_rows = session.run(
                """
                MATCH (node:Section {uid: $source_id})
                OPTIONAL MATCH (parent:Section)-[:HAS_SUBSECTION]->(node)
                RETURN parent.uid AS source_id,
                       elementId(parent) AS runtime_locator,
                       parent.section_number AS section_number,
                       parent.title AS heading,
                       parent.content AS content
                """,
                source_id=source_id,
            ).data()
            table_rows: list[dict[str, Any]] = []
            if include_table:
                table_rows = session.run(
                    """
                    MATCH (node:Section {uid: $source_id})-[:HAS_TABLE]->(table:Table)
                    RETURN elementId(table) AS runtime_locator,
                           table.title AS heading,
                           table.description AS content
                    ORDER BY heading, runtime_locator
                    """,
                    source_id=source_id,
                ).data()
        for row in parent_rows:
            parent_id = str(row.get("source_id") or "")
            if not parent_id:
                continue
            content = "\n".join(
                value
                for value in (
                    " ".join(
                        value
                        for value in (
                            str(row.get("section_number") or "").strip(),
                            str(row.get("heading") or "").strip(),
                        )
                        if value
                    ),
                    str(row.get("content") or "").strip(),
                )
                if value
            )
            items.append(
                ContextItem(
                    context_id=f"{source_id}:parent:{parent_id}",
                    seed_source_id=source_id,
                    source_id=parent_id,
                    document_id=seed.document_id,
                    context_type=ContextType.IMMEDIATE_PARENT,
                    content=content,
                    provenance={
                        "runtime_locator": str(row.get("runtime_locator") or ""),
                        "relationship": "HAS_SUBSECTION",
                    },
                )
            )
        for row in table_rows:
            heading = str(row.get("heading") or "")
            content = str(row.get("content") or "")
            table_id = _derived_id("chemical-table", source_id, heading, content)
            items.append(
                ContextItem(
                    context_id=f"{source_id}:table:{table_id}",
                    seed_source_id=source_id,
                    source_id=table_id,
                    document_id=seed.document_id,
                    context_type=ContextType.TABLE,
                    content="\n".join(value for value in (heading, content) if value),
                    provenance={
                        "runtime_locator": str(row.get("runtime_locator") or ""),
                        "relationship": "HAS_TABLE",
                    },
                )
            )
        return items

    def get_graph_metadata(self, source_ids: list[str]) -> dict[str, GraphMetadata]:
        if not source_ids:
            return {}
        with self._driver.session(**self._session_parameters()) as session:
            rows = session.run(
                """
                UNWIND $source_ids AS source_id
                MATCH (source:Section {uid: source_id})
                OPTIONAL MATCH (source)-[rel:CITES|DEPENDS_ON]->(target:Section)
                WHERE toFloat(rel.confidence) >= $minimum_confidence
                RETURN source_id,
                       count(DISTINCT target.uid) AS eligible_count,
                       [value IN collect(DISTINCT type(rel)) WHERE value IS NOT NULL]
                           AS relation_types,
                       max(toFloat(rel.confidence)) AS maximum_confidence
                ORDER BY source_id
                """,
                source_ids=source_ids,
                minimum_confidence=0.85,
            ).data()
        by_id = {
            str(row["source_id"]): GraphMetadata(
                source_id=str(row["source_id"]),
                eligible_outgoing_count=int(row.get("eligible_count") or 0),
                relation_types=tuple(sorted(row.get("relation_types") or [])),
                maximum_confidence=(
                    None
                    if row.get("maximum_confidence") is None
                    else float(row["maximum_confidence"])
                ),
            )
            for row in rows
        }
        missing = sorted(set(source_ids) - set(by_id))
        if missing:
            raise KeyError(f"unknown chemical source IDs: {missing}")
        return {source_id: by_id[source_id] for source_id in source_ids}

    def expand_graph(
        self, source_ids: list[str], *, minimum_confidence: float = 0.85
    ) -> list[GraphTarget]:
        if not source_ids:
            return []
        with self._driver.session(**self._session_parameters()) as session:
            rows = session.run(
                """
                UNWIND range(0, size($source_ids) - 1) AS seed_rank
                MATCH (source:Section {uid: $source_ids[seed_rank]})
                MATCH (source)-[rel:CITES|DEPENDS_ON]->(target:Section)
                WHERE toFloat(rel.confidence) >= $minimum_confidence
                OPTIONAL MATCH (standard:Standard {uid: target.standard_uid})
                RETURN source.uid AS seed_source_id,
                       target.uid AS source_id,
                       elementId(target) AS runtime_locator,
                       coalesce(
                           standard.standard_id, standard.uid,
                           target.standard_uid, target.raw_standard_id, target.doc_id
                       ) AS document_id,
                       target.section_number AS section_number,
                       target.title AS heading,
                       target.content AS content,
                       type(rel) AS relation_type,
                       toFloat(rel.confidence) AS confidence,
                       seed_rank
                ORDER BY seed_rank, confidence DESC, relation_type, source_id
                """,
                source_ids=source_ids,
                minimum_confidence=minimum_confidence,
            ).data()
        result: list[GraphTarget] = []
        seen = set(source_ids)
        for row in rows:
            target = self._section_from_row(row)
            if target.source_id in seen:
                continue
            seen.add(target.source_id)
            relation_type = str(row["relation_type"])
            result.append(
                GraphTarget(
                    seed_source_id=str(row["seed_source_id"]),
                    target=target,
                    relation_type_original=relation_type,
                    relation_type_normalized=relation_type,
                    confidence=float(row["confidence"]),
                    provenance={
                        "source_runtime_relation": relation_type,
                        "target_runtime_locator": target.runtime_locator,
                    },
                )
            )
        return result

    def manual_corpus_search(self, query: str, limit: int = 100) -> list[RetrievalCandidate]:
        return self.bm25_search(query, limit=limit)
