"""Post hoc construction-artifact diagnostics, excluded from router inputs."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from evidence_routing.metrics import PathOutcome
from evidence_routing.schemas import QueryRecord


def summarize_by_construction_category(
    queries: Sequence[QueryRecord], outcomes: Sequence[PathOutcome]
) -> dict[str, Any]:
    """Summarize frozen outcomes by authoring stratum without model reuse."""
    query_map = {query.question_id: query for query in queries}
    if len(query_map) != len(queries):
        raise ValueError("queries must have unique identities")
    if any(outcome.question_id not in query_map for outcome in outcomes):
        raise ValueError("outcome has no matching query")
    grouped: dict[tuple[str, str, str], list[PathOutcome]] = defaultdict(list)
    by_identity = {}
    for outcome in outcomes:
        query = query_map[outcome.question_id]
        key = (
            query.domain.value,
            query.construction_category.value,
            outcome.path_id,
        )
        grouped[key].append(outcome)
        by_identity[(outcome.question_id, outcome.path_id)] = outcome
    summaries: dict[str, Any] = defaultdict(lambda: defaultdict(dict))
    for (domain, category, path_id), rows in sorted(grouped.items()):
        count = len(rows)
        summaries[domain][category][path_id] = {
            "question_count": count,
            "evidence_completeness_rate": sum(row.evidence_complete for row in rows) / count,
            "harmful_expansion_rate": sum(row.harmful_expansion for row in rows) / count,
            "combined_path_success_rate": sum(row.combined_path_success for row in rows) / count,
        }
    stage_pairs = {
        "reranking_P1_minus_P0": ("P0", "P1"),
        "context_P2_minus_P0": ("P0", "P2"),
        "context_P4_minus_P1": ("P1", "P4"),
        "graph_P3_minus_P0": ("P0", "P3"),
        "graph_P5_minus_P4": ("P4", "P5"),
    }
    rescues: dict[str, Any] = defaultdict(lambda: defaultdict(dict))
    for query in queries:
        for stage, (before, after) in stage_pairs.items():
            rescued = (
                not by_identity[(query.question_id, before)].combined_path_success
                and by_identity[(query.question_id, after)].combined_path_success
            )
            domain = query.domain.value
            category = query.construction_category.value
            row = rescues[domain][category].setdefault(
                stage, {"rescued_count": 0, "question_count": 0}
            )
            row["question_count"] += 1
            row["rescued_count"] += int(rescued)
    return {
        "feature_use_prohibited": True,
        "path_outcomes": {domain: dict(categories) for domain, categories in summaries.items()},
        "stage_rescues": {domain: dict(categories) for domain, categories in rescues.items()},
    }
