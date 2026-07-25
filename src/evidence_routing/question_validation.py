"""Cross-record validation for the path-blind pre-freeze authoring batch."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher

from evidence_routing.adapters.base import RegulatoryCorpusAdapter
from evidence_routing.authoring import (
    AuthoringRecord,
    ManualSearchRecord,
    PriorQuestionCheck,
    ReviewDecision,
    SearchConclusion,
)
from evidence_routing.schemas import (
    ConstructionCategory,
    ContextType,
    Domain,
    EvidenceSpecification,
    QueryRecord,
)
from evidence_routing.validation import DatasetValidationError, ValidationIssue

PREFREEZE_QUESTION_QUOTAS: dict[tuple[Domain, ConstructionCategory], int] = {
    (Domain.CHEMICAL, ConstructionCategory.DIRECT_CLAUSE): 2,
    (Domain.CHEMICAL, ConstructionCategory.PARENT_HEADING_CONTEXT): 2,
    (Domain.CHEMICAL, ConstructionCategory.TABLE_RELATED): 2,
    (Domain.CHEMICAL, ConstructionCategory.CITATION_DEPENDENCY): 2,
    (Domain.CHEMICAL, ConstructionCategory.EVIDENCE_INSUFFICIENT): 2,
    (Domain.PHARMACEUTICAL, ConstructionCategory.DIRECT_CLAUSE): 3,
    (Domain.PHARMACEUTICAL, ConstructionCategory.PARENT_HEADING_CONTEXT): 3,
    (Domain.PHARMACEUTICAL, ConstructionCategory.TABLE_RELATED): 2,
    (Domain.PHARMACEUTICAL, ConstructionCategory.CITATION_DEPENDENCY): 0,
    (Domain.PHARMACEUTICAL, ConstructionCategory.EVIDENCE_INSUFFICIENT): 2,
}


@dataclass(frozen=True, slots=True)
class PriorQuestionFlag:
    question_id: str
    prior_id: str
    normalized_similarity: float


def normalize_question_text(value: str) -> str:
    """Normalize punctuation, case, and whitespace without translating text."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(re.findall(r"[\w]+", normalized, flags=re.UNICODE))


def find_prior_question_flags(
    queries: Iterable[QueryRecord],
    prior_questions: Mapping[str, str],
    *,
    threshold: float = 0.85,
) -> tuple[PriorQuestionFlag, ...]:
    """Return deterministic high-overlap flags; exact matches are included."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("prior-question threshold must be in [0, 1]")
    normalized_prior = {
        prior_id: normalize_question_text(text)
        for prior_id, text in prior_questions.items()
    }
    flags: list[PriorQuestionFlag] = []
    for query in queries:
        current = normalize_question_text(query.query_text)
        for prior_id, prior in normalized_prior.items():
            score = SequenceMatcher(None, current, prior).ratio()
            if score >= threshold:
                flags.append(
                    PriorQuestionFlag(
                        question_id=query.question_id,
                        prior_id=prior_id,
                        normalized_similarity=score,
                    )
                )
    return tuple(
        sorted(
            flags,
            key=lambda row: (
                row.question_id,
                -row.normalized_similarity,
                row.prior_id,
            ),
        )
    )


def _indexed(records, key_name: str, issues: list[ValidationIssue]):
    result = {}
    for record in records:
        key = getattr(record, key_name)
        if key in result:
            issues.append(ValidationIssue("E_AUTHORING_ID_DUPLICATE", str(key)))
        result[key] = record
    return result


def _resolvable_evidence_ids(
    adapter: RegulatoryCorpusAdapter,
    query: QueryRecord,
    issues: list[ValidationIssue],
) -> tuple[set[str], dict[ContextType, set[str]], set[str]]:
    anchors: set[str] = set()
    contexts: dict[ContextType, set[str]] = {
        ContextType.HEADING_PATH: set(),
        ContextType.IMMEDIATE_PARENT: set(),
        ContextType.TABLE: set(),
    }
    graph_targets: set[str] = set()
    for source_id in query.authoring_source_ids:
        try:
            section = adapter.get_section(source_id)
        except (KeyError, RuntimeError, ValueError):
            issues.append(
                ValidationIssue(
                    "E_AUTHORING_SOURCE_UNRESOLVED",
                    f"question={query.question_id}; source={source_id}",
                )
            )
            continue
        if section.domain != query.domain:
            issues.append(
                ValidationIssue(
                    "E_AUTHORING_SOURCE_DOMAIN",
                    f"question={query.question_id}; source={source_id}",
                )
            )
            continue
        anchors.add(source_id)
        try:
            for item in adapter.get_context_sidecars(source_id, include_table=True):
                if item.seed_source_id == source_id and item.content.strip():
                    contexts[item.context_type].add(item.source_id)
            for target in adapter.expand_graph([source_id], minimum_confidence=0.85):
                if (
                    target.seed_source_id == source_id
                    and target.relation_type_normalized in {"CITES", "DEPENDS_ON"}
                    and target.confidence >= 0.85
                ):
                    graph_targets.add(target.target.source_id)
        except (KeyError, RuntimeError, ValueError):
            issues.append(
                ValidationIssue(
                    "E_AUTHORING_STRUCTURE_UNRESOLVED",
                    f"question={query.question_id}; source={source_id}",
                )
            )
    return anchors, contexts, graph_targets


def validate_authoring_batch(
    queries: list[QueryRecord],
    specifications: list[EvidenceSpecification],
    authoring_records: list[AuthoringRecord],
    manual_searches: list[ManualSearchRecord],
    *,
    adapters: Mapping[Domain, RegulatoryCorpusAdapter],
    prior_questions: Mapping[str, str] | None = None,
    expected_quotas: Mapping[
        tuple[Domain, ConstructionCategory], int
    ] = PREFREEZE_QUESTION_QUOTAS,
    require_accepted: bool = False,
) -> tuple[PriorQuestionFlag, ...]:
    """Validate one complete path-blind batch and return non-blocking overlap flags."""
    issues: list[ValidationIssue] = []
    required_keys = {
        (domain, category) for domain in Domain for category in ConstructionCategory
    }
    if set(expected_quotas) != required_keys or any(
        count < 0 for count in expected_quotas.values()
    ):
        raise ValueError("expected_quotas must define all non-negative cells")

    query_by_id = _indexed(queries, "question_id", issues)
    specification_by_id = _indexed(specifications, "question_id", issues)
    authoring_by_id = _indexed(authoring_records, "question_id", issues)
    manual_by_question = _indexed(manual_searches, "question_id", issues)
    identities = (set(query_by_id), set(specification_by_id), set(authoring_by_id))
    if len({frozenset(values) for values in identities}) != 1:
        issues.append(ValidationIssue("E_AUTHORING_RECORD_MISMATCH", "question IDs differ"))

    actual = Counter((row.domain, row.construction_category) for row in queries)
    for (domain, category), expected in expected_quotas.items():
        if actual[(domain, category)] != expected:
            issues.append(
                ValidationIssue(
                    "E_PREFREEZE_QUOTA",
                    f"domain={domain.value}; category={category.value}; "
                    f"expected={expected}; actual={actual[(domain, category)]}",
                )
            )

    normalized = [normalize_question_text(row.query_text) for row in queries]
    duplicate_texts = sorted(
        text for text, count in Counter(normalized).items() if count > 1
    )
    for text in duplicate_texts:
        issues.append(ValidationIssue("E_QUERY_TEXT_DUPLICATE", text))

    for question_id in sorted(set.intersection(*identities) if identities else set()):
        query = query_by_id[question_id]
        specification = specification_by_id[question_id]
        authoring = authoring_by_id[question_id]
        if (
            authoring.specification_id != specification.specification_id
            or authoring.domain != query.domain
            or authoring.construction_category != query.construction_category
        ):
            issues.append(
                ValidationIssue("E_AUTHORING_IDENTITY_MISMATCH", question_id)
            )
        if require_accepted and authoring.review_decision != ReviewDecision.ACCEPT:
            issues.append(ValidationIssue("E_REVIEW_NOT_ACCEPTED", question_id))

        if query.construction_category == ConstructionCategory.EVIDENCE_INSUFFICIENT:
            search = manual_by_question.get(question_id)
            if (
                search is None
                or search.domain != query.domain
                or search.conclusion != SearchConclusion.CORPUS_INSUFFICIENT
                or search.evidence_found
                or authoring.manual_search_record_id != search.manual_search_id
            ):
                issues.append(ValidationIssue("E_MANUAL_SEARCH_REQUIRED", question_id))
            continue

        if not query.authoring_source_ids:
            issues.append(ValidationIssue("E_AUTHORING_SOURCE_MISSING", question_id))
            continue
        adapter = adapters.get(query.domain)
        if adapter is None:
            issues.append(
                ValidationIssue("E_AUTHORING_ADAPTER_MISSING", query.domain.value)
            )
            continue
        anchors, contexts, graph_targets = _resolvable_evidence_ids(
            adapter, query, issues
        )
        evidence_ids = set(
            specification.required_source_ids + specification.sufficient_source_ids
        )
        resolvable = anchors | graph_targets | set().union(*contexts.values())
        missing = sorted(evidence_ids - resolvable)
        if missing:
            issues.append(
                ValidationIssue(
                    "E_EVIDENCE_SOURCE_UNRESOLVED",
                    f"question={question_id}; sources={missing}",
                )
            )
        category = query.construction_category
        if category == ConstructionCategory.DIRECT_CLAUSE and not evidence_ids <= anchors:
            issues.append(ValidationIssue("E_DIRECT_STRUCTURE", question_id))
        if category == ConstructionCategory.PARENT_HEADING_CONTEXT and not evidence_ids & (
            contexts[ContextType.HEADING_PATH]
            | contexts[ContextType.IMMEDIATE_PARENT]
        ):
            issues.append(ValidationIssue("E_CONTEXT_STRUCTURE", question_id))
        if category == ConstructionCategory.TABLE_RELATED and not evidence_ids & contexts[
            ContextType.TABLE
        ]:
            issues.append(ValidationIssue("E_TABLE_STRUCTURE", question_id))
        if category == ConstructionCategory.CITATION_DEPENDENCY and not evidence_ids & (
            graph_targets
        ):
            issues.append(ValidationIssue("E_GRAPH_STRUCTURE", question_id))

    flags = find_prior_question_flags(queries, prior_questions or {})
    exact_flagged = {
        row.question_id for row in flags if row.normalized_similarity == 1.0
    }
    for question_id in sorted(exact_flagged):
        issues.append(ValidationIssue("E_PRIOR_QUESTION_EXACT", question_id))
    if require_accepted:
        for question_id, authoring in sorted(authoring_by_id.items()):
            if authoring.prior_question_check != PriorQuestionCheck.CLEAR:
                issues.append(
                    ValidationIssue("E_PRIOR_CHECK_STATE", question_id)
                )
    if issues:
        raise DatasetValidationError(issues)
    return flags
