"""Unified read-only contract implemented by both regulatory corpora."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

from evidence_routing.schemas import ContextType, Domain


@dataclass(frozen=True, slots=True)
class CorpusManifest:
    domain: Domain
    corpus_hash: str
    record_count: int
    source_revision: str


@dataclass(frozen=True, slots=True)
class SourceSection:
    domain: Domain
    source_id: str
    document_id: str
    heading: str
    content: str
    source_type: str
    runtime_locator: str
    provenance: dict[str, str]


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    section: SourceSection
    rank: int
    score: float


@dataclass(frozen=True, slots=True)
class ContextItem:
    context_id: str
    seed_source_id: str
    source_id: str
    document_id: str
    context_type: ContextType
    content: str
    provenance: dict[str, str]


@dataclass(frozen=True, slots=True)
class GraphMetadata:
    source_id: str
    eligible_outgoing_count: int
    relation_types: tuple[str, ...]
    maximum_confidence: float | None


@dataclass(frozen=True, slots=True)
class GraphTarget:
    seed_source_id: str
    target: SourceSection
    relation_type_original: str
    relation_type_normalized: str
    confidence: float
    provenance: dict[str, str]


class RegulatoryCorpusAdapter(ABC):
    """Small interface required by the frozen Pilot paths."""

    @abstractmethod
    def corpus_manifest(self) -> CorpusManifest:
        """Return immutable corpus identity without copying source data."""

    @abstractmethod
    def bm25_search(self, query: str, limit: int = 50) -> list[RetrievalCandidate]:
        """Run the domain's frozen BM25 implementation."""

    @abstractmethod
    def get_section(self, source_id: str) -> SourceSection:
        """Resolve exactly one stable source identifier."""

    @abstractmethod
    def get_context_sidecars(self, source_id: str, *, include_table: bool) -> list[ContextItem]:
        """Return deterministic heading, parent, and eligible table context."""

    @abstractmethod
    def get_graph_metadata(self, source_ids: list[str]) -> dict[str, GraphMetadata]:
        """Return bounded relation metadata without fetching target text."""

    @abstractmethod
    def expand_graph(
        self, source_ids: list[str], *, minimum_confidence: float = 0.85
    ) -> list[GraphTarget]:
        """Follow only frozen, eligible one-hop outgoing relations."""

    @abstractmethod
    def manual_corpus_search(self, query: str, limit: int = 100) -> list[RetrievalCandidate]:
        """Support documented human corpus checks; never infer insufficiency."""


def dataclass_payload(value: Any) -> Any:
    """Convert nested adapter dataclasses into JSON-safe deterministic payloads."""
    if hasattr(value, "__dataclass_fields__"):
        return {key: dataclass_payload(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): dataclass_payload(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [dataclass_payload(item) for item in value]
    if isinstance(value, Domain | ContextType):
        return value.value
    return value
