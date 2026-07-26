from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from evidence_routing.authoring import AuthoringRecord
from evidence_routing.freeze import append_correction, freeze_queries
from evidence_routing.schemas import (
    ConstructionCategory,
    Domain,
    EvidenceSpecification,
    QueryRecord,
)

HASH = "a" * 64
NOW = datetime.fromisoformat("2026-07-26T10:00:00+08:00")


def _batch(text: str = "What requirement applies?"):
    question_id = "PHARMA-FREEZE-001"
    query = QueryRecord(
        question_id=question_id,
        domain=Domain.PHARMACEUTICAL,
        language="en",
        query_text=text,
        construction_category=ConstructionCategory.DIRECT_CLAUSE,
        source_group_id="DOC-1",
        authoring_source_ids=["SOURCE-1"],
    )
    specification = EvidenceSpecification(
        question_id=question_id,
        specification_id="SPEC-1",
        required_source_ids=["SOURCE-1"],
        evidence_scope_note="The direct clause is required.",
    )
    authoring = AuthoringRecord(
        authoring_id="AUTHOR-1",
        question_id=question_id,
        specification_id="SPEC-1",
        domain=Domain.PHARMACEUTICAL,
        construction_category=ConstructionCategory.DIRECT_CLAUSE,
        review_decision="accept",
        construction_rationale="A direct clause supplies the complete answer.",
        prior_question_check="clear",
        source_resolution_checked=True,
        reviewed_by="REVIEWER-1",
        reviewed_at=NOW,
    )
    return [query], [specification], [authoring], []


def _freeze(tmp_path: Path, name: str, text: str = "What requirement applies?"):
    protocol = tmp_path / "protocol.yaml"
    config = tmp_path / "config.yaml"
    prior = tmp_path / "prior.json"
    for path, value in (
        (protocol, "protocol: 1\n"),
        (config, "seed: 1\n"),
        (prior, "[]\n"),
    ):
        if not path.exists():
            path.write_text(value, encoding="utf-8")
    queries, specifications, authoring, searches = _batch(text)
    quota = {
        (domain, category): int(
            domain == Domain.PHARMACEUTICAL
            and category == ConstructionCategory.DIRECT_CLAUSE
        )
        for domain in Domain
        for category in ConstructionCategory
    }
    return freeze_queries(
        tmp_path / name,
        batch_id=name,
        queries=queries,
        specifications=specifications,
        authoring_records=authoring,
        manual_searches=searches,
        protocol_path=protocol,
        configuration_paths={"config": config},
        corpus_hashes={"chemical": HASH, "pharmaceutical": HASH},
        prior_inventory_paths={"prior": prior},
        frozen_at=NOW,
        expected_quotas=quota,
    )


def test_freeze_is_idempotent_but_refuses_different_content(tmp_path: Path) -> None:
    first = _freeze(tmp_path, "pilot-v1")
    repeated = _freeze(tmp_path, "pilot-v1")
    assert repeated.batch_hash == first.batch_hash
    with pytest.raises(FileExistsError):
        _freeze(tmp_path, "pilot-v1", "Which different requirement applies?")


def test_freeze_rejects_unaccepted_question(tmp_path: Path) -> None:
    protocol = tmp_path / "protocol.yaml"
    protocol.write_text("protocol: 1\n", encoding="utf-8")
    queries, specifications, authoring, searches = _batch()
    authoring[0] = authoring[0].model_copy(
        update={"review_decision": "ready_for_review", "reviewed_by": None, "reviewed_at": None}
    )
    quota = {
        (domain, category): int(
            domain == Domain.PHARMACEUTICAL
            and category == ConstructionCategory.DIRECT_CLAUSE
        )
        for domain in Domain
        for category in ConstructionCategory
    }
    with pytest.raises(ValueError, match="not accepted"):
        freeze_queries(
            tmp_path / "batch",
            batch_id="batch",
            queries=queries,
            specifications=specifications,
            authoring_records=authoring,
            manual_searches=searches,
            protocol_path=protocol,
            configuration_paths={"protocol": protocol},
            corpus_hashes={"chemical": HASH, "pharmaceutical": HASH},
            prior_inventory_paths={"prior": protocol},
            frozen_at=NOW,
            expected_quotas=quota,
        )


def test_correction_is_hash_chained_and_invalidates_runs(tmp_path: Path) -> None:
    previous = _freeze(tmp_path, "pilot-v1")
    replacement = _freeze(
        tmp_path, "pilot-v2", "Which corrected requirement applies?"
    )
    ledger = tmp_path / "corrections.json"
    first = append_correction(
        ledger,
        previous=previous,
        replacement=replacement,
        changed_question_ids=["PHARMA-FREEZE-001"],
        reason="The frozen wording required a material correction.",
        corrected_by="REVIEWER-1",
        corrected_at=NOW,
        invalidated_run_hashes={"RUN-1": HASH},
    )
    assert first.invalidated_run_hashes == {"RUN-1": HASH}
    assert first.previous_entry_hash is None
    third = _freeze(tmp_path, "pilot-v3", "What final requirement applies?")
    second = append_correction(
        ledger,
        previous=replacement,
        replacement=third,
        changed_question_ids=["PHARMA-FREEZE-001"],
        reason="A second material correction was required.",
        corrected_by="REVIEWER-1",
        corrected_at=NOW,
        invalidated_run_hashes={},
    )
    assert second.previous_entry_hash == first.entry_hash
