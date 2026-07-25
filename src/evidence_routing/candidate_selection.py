"""Path-blind discovery of evidence structures for human question authoring."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from evidence_routing.adapters.base import (
    ContextItem,
    CorpusManifest,
    GraphTarget,
    RegulatoryCorpusAdapter,
    SourceSection,
)
from evidence_routing.schemas import ConstructionCategory, ContextType, Domain

_SUPPORTED_CATEGORIES = (
    ConstructionCategory.DIRECT_CLAUSE,
    ConstructionCategory.PARENT_HEADING_CONTEXT,
    ConstructionCategory.TABLE_RELATED,
    ConstructionCategory.CITATION_DEPENDENCY,
)
_ELIGIBLE_RELATIONS = {"CITES", "DEPENDS_ON"}


@dataclass(frozen=True, slots=True)
class CorpusExpectation:
    domain: Domain
    corpus_hash: str
    record_count: int
    source_revision: str


@dataclass(frozen=True, slots=True)
class CandidateStructure:
    candidate_id: str
    domain: Domain
    proposed_category: ConstructionCategory
    source_group_id: str
    anchor_source_id: str
    evidence_source_ids: tuple[str, ...]
    context_type: ContextType | None
    relation_type: str | None
    relation_confidence: float | None
    anchor_character_count: int
    supporting_character_count: int

    def to_safe_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["domain"] = self.domain.value
        payload["proposed_category"] = self.proposed_category.value
        payload["context_type"] = (
            None if self.context_type is None else self.context_type.value
        )
        return payload


def verify_corpus_manifest(
    actual: CorpusManifest,
    expected: CorpusExpectation,
) -> None:
    """Require exact immutable corpus identity before candidate discovery."""
    mismatches: list[str] = []
    for field in ("domain", "corpus_hash", "record_count", "source_revision"):
        if getattr(actual, field) != getattr(expected, field):
            mismatches.append(field)
    if mismatches:
        raise ValueError(
            "candidate selection corpus mismatch: " + ", ".join(sorted(mismatches))
        )


def _candidate_id(
    domain: Domain,
    category: ConstructionCategory,
    source_ids: tuple[str, ...],
) -> str:
    digest = hashlib.sha256(
        "\0".join((domain.value, category.value, *source_ids)).encode("utf-8")
    ).hexdigest()[:20]
    prefix = "CHEM" if domain == Domain.CHEMICAL else "PHARMA"
    return f"CAND-{prefix}-{category.value.upper()}-{digest}"


def _validate_section(section: SourceSection, expected_domain: Domain) -> None:
    if section.domain != expected_domain:
        raise ValueError(
            f"source domain mismatch: expected={expected_domain.value} "
            f"actual={section.domain.value}"
        )
    if not section.source_id or not section.document_id:
        raise ValueError("candidate source lacks stable identity")
    if not section.heading.strip() and not section.content.strip():
        raise ValueError(f"candidate source has no attributable text: {section.source_id}")
    if not section.provenance.get("corpus_hash"):
        raise ValueError(f"candidate source lacks corpus provenance: {section.source_id}")


def _direct_structure(section: SourceSection) -> CandidateStructure:
    source_ids = (section.source_id,)
    return CandidateStructure(
        candidate_id=_candidate_id(
            section.domain,
            ConstructionCategory.DIRECT_CLAUSE,
            source_ids,
        ),
        domain=section.domain,
        proposed_category=ConstructionCategory.DIRECT_CLAUSE,
        source_group_id=section.document_id,
        anchor_source_id=section.source_id,
        evidence_source_ids=source_ids,
        context_type=None,
        relation_type=None,
        relation_confidence=None,
        anchor_character_count=len(section.content.strip()),
        supporting_character_count=0,
    )


def _context_structure(
    section: SourceSection,
    item: ContextItem,
) -> CandidateStructure:
    if item.seed_source_id != section.source_id:
        raise ValueError(f"context seed mismatch for {item.context_id}")
    if not item.context_id or not item.source_id or not item.document_id:
        raise ValueError("context candidate lacks stable identity")
    if not item.content.strip():
        raise ValueError(f"context candidate has no attributable text: {item.context_id}")
    category = (
        ConstructionCategory.TABLE_RELATED
        if item.context_type == ContextType.TABLE
        else ConstructionCategory.PARENT_HEADING_CONTEXT
    )
    if item.context_type not in {
        ContextType.HEADING_PATH,
        ContextType.IMMEDIATE_PARENT,
        ContextType.TABLE,
    }:
        raise ValueError(f"unsupported context type: {item.context_type}")
    source_ids = (section.source_id, item.source_id)
    return CandidateStructure(
        candidate_id=_candidate_id(section.domain, category, source_ids),
        domain=section.domain,
        proposed_category=category,
        source_group_id=section.document_id,
        anchor_source_id=section.source_id,
        evidence_source_ids=source_ids,
        context_type=item.context_type,
        relation_type=None,
        relation_confidence=None,
        anchor_character_count=len(section.content.strip()),
        supporting_character_count=len(item.content.strip()),
    )


def _graph_structure(
    section: SourceSection,
    target: GraphTarget,
    *,
    minimum_confidence: float,
) -> CandidateStructure:
    if target.seed_source_id != section.source_id:
        raise ValueError(f"graph seed mismatch for {target.target.source_id}")
    if target.relation_type_normalized not in _ELIGIBLE_RELATIONS:
        raise ValueError(
            f"unsupported graph relation: {target.relation_type_normalized}"
        )
    if not minimum_confidence <= float(target.confidence) <= 1.0:
        raise ValueError(
            f"ineligible graph confidence for {target.target.source_id}: "
            f"{target.confidence}"
        )
    _validate_section(target.target, section.domain)
    source_ids = (section.source_id, target.target.source_id)
    return CandidateStructure(
        candidate_id=_candidate_id(
            section.domain,
            ConstructionCategory.CITATION_DEPENDENCY,
            source_ids,
        ),
        domain=section.domain,
        proposed_category=ConstructionCategory.CITATION_DEPENDENCY,
        source_group_id=section.document_id,
        anchor_source_id=section.source_id,
        evidence_source_ids=source_ids,
        context_type=None,
        relation_type=target.relation_type_normalized,
        relation_confidence=float(target.confidence),
        anchor_character_count=len(section.content.strip()),
        supporting_character_count=len(target.target.content.strip()),
    )


def inspect_source(
    adapter: RegulatoryCorpusAdapter,
    source_id: str,
    *,
    minimum_graph_confidence: float = 0.85,
) -> tuple[CandidateStructure, ...]:
    """Describe attributable structures around one source without running a path."""
    if minimum_graph_confidence != 0.85:
        raise ValueError("the frozen Pilot graph confidence is 0.85")
    section = adapter.get_section(source_id)
    _validate_section(section, adapter.corpus_manifest().domain)
    structures = [_direct_structure(section)]
    for item in adapter.get_context_sidecars(source_id, include_table=True):
        structures.append(_context_structure(section, item))
    for target in adapter.expand_graph(
        [source_id],
        minimum_confidence=minimum_graph_confidence,
    ):
        structures.append(
            _graph_structure(
                section,
                target,
                minimum_confidence=minimum_graph_confidence,
            )
        )
    return tuple(
        sorted(
            structures,
            key=lambda row: (
                _SUPPORTED_CATEGORIES.index(row.proposed_category),
                row.evidence_source_ids,
                row.candidate_id,
            ),
        )
    )


def select_candidate_structures(
    adapter: RegulatoryCorpusAdapter,
    source_ids: Iterable[str],
    *,
    expected_corpus: CorpusExpectation,
    limits: Mapping[ConstructionCategory, int] | None = None,
) -> tuple[CandidateStructure, ...]:
    """Select deterministic per-category candidates from supplied source IDs."""
    verify_corpus_manifest(adapter.corpus_manifest(), expected_corpus)
    category_limits = {
        category: 10 for category in _SUPPORTED_CATEGORIES
    }
    if limits is not None:
        unknown = set(limits) - set(_SUPPORTED_CATEGORIES)
        if unknown:
            raise ValueError(f"unsupported candidate categories: {sorted(unknown)}")
        for category, limit in limits.items():
            if limit < 0:
                raise ValueError("candidate limits must be non-negative")
            category_limits[category] = int(limit)

    selected: dict[ConstructionCategory, list[CandidateStructure]] = {
        category: [] for category in _SUPPORTED_CATEGORIES
    }
    seen_candidates: set[str] = set()
    seen_groups: dict[ConstructionCategory, set[str]] = {
        category: set() for category in _SUPPORTED_CATEGORIES
    }
    normalized_ids = sorted({value.strip() for value in source_ids if value.strip()})
    for source_id in normalized_ids:
        if all(
            len(selected[category]) >= category_limits[category]
            for category in _SUPPORTED_CATEGORIES
        ):
            break
        for structure in inspect_source(adapter, source_id):
            category = structure.proposed_category
            if len(selected[category]) >= category_limits[category]:
                continue
            if structure.candidate_id in seen_candidates:
                continue
            if structure.source_group_id in seen_groups[category]:
                continue
            selected[category].append(structure)
            seen_candidates.add(structure.candidate_id)
            seen_groups[category].add(structure.source_group_id)

    return tuple(
        structure
        for category in _SUPPORTED_CATEGORIES
        for structure in selected[category]
    )
