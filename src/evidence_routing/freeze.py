"""Immutable private batch freezes and append-only correction records."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from evidence_routing.authoring import (
    AuthoringRecord,
    ManualSearchRecord,
    PriorQuestionCheck,
    ReviewDecision,
    SearchConclusion,
)
from evidence_routing.question_validation import (
    PREFREEZE_QUESTION_QUOTAS,
    normalize_question_text,
)
from evidence_routing.schemas import (
    ConstructionCategory,
    Domain,
    EvidenceSpecification,
    QueryRecord,
    StrictModel,
)

Hash = str


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> Hash:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> Hash:
    return _sha256_bytes(path.read_bytes())


def _model_rows(records: Sequence[StrictModel], identity: str) -> list[dict[str, Any]]:
    return [
        row.model_dump(mode="json")
        for row in sorted(records, key=lambda item: str(getattr(item, identity)))
    ]


class FrozenBatchManifest(StrictModel):
    """Content identity and dependencies for one immutable question batch."""

    batch_id: str = Field(min_length=1, max_length=128)
    frozen_at: datetime
    question_count: int = Field(gt=0)
    question_ids: list[str] = Field(min_length=1)
    record_hashes: dict[str, Hash] = Field(min_length=1)
    protocol_hash: Hash = Field(pattern=r"^[a-f0-9]{64}$")
    configuration_hashes: dict[str, Hash] = Field(min_length=1)
    corpus_hashes: dict[str, Hash]
    prior_inventory_hashes: dict[str, Hash] = Field(min_length=1)
    batch_hash: Hash = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_manifest(self) -> FrozenBatchManifest:
        if self.frozen_at.utcoffset() is None:
            raise ValueError("frozen_at must include a timezone")
        if self.question_count != len(self.question_ids):
            raise ValueError("question_count must match question_ids")
        if len(set(self.question_ids)) != len(self.question_ids):
            raise ValueError("question_ids must be unique")
        for mapping in (
            self.record_hashes,
            self.configuration_hashes,
            self.corpus_hashes,
            self.prior_inventory_hashes,
        ):
            if any(
                len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
                for value in mapping.values()
            ):
                raise ValueError("manifest dependencies must be lowercase SHA-256 values")
        return self


class CorrectionLedgerEntry(StrictModel):
    """Hash-chained record invalidating outputs from a replaced frozen batch."""

    correction_id: str = Field(min_length=1, max_length=128)
    previous_batch_id: str
    previous_batch_hash: Hash = Field(pattern=r"^[a-f0-9]{64}$")
    replacement_batch_id: str
    replacement_batch_hash: Hash = Field(pattern=r"^[a-f0-9]{64}$")
    changed_question_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=10, max_length=1000)
    corrected_by: str
    corrected_at: datetime
    invalidated_run_hashes: dict[str, Hash]
    previous_entry_hash: Hash | None = Field(
        default=None, pattern=r"^[a-f0-9]{64}$"
    )
    entry_hash: Hash = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_correction(self) -> CorrectionLedgerEntry:
        if self.corrected_at.utcoffset() is None:
            raise ValueError("corrected_at must include a timezone")
        if self.previous_batch_hash == self.replacement_batch_hash:
            raise ValueError("a correction must change the frozen batch")
        if len(set(self.changed_question_ids)) != len(self.changed_question_ids):
            raise ValueError("changed_question_ids must be unique")
        if any(
            len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in self.invalidated_run_hashes.values()
        ):
            raise ValueError("invalidated run hashes must be lowercase SHA-256 values")
        return self


def _validate_freeze_inputs(
    queries: Sequence[QueryRecord],
    specifications: Sequence[EvidenceSpecification],
    authoring_records: Sequence[AuthoringRecord],
    manual_searches: Sequence[ManualSearchRecord],
    expected_quotas: Mapping[tuple[Domain, ConstructionCategory], int],
) -> None:
    if len(queries) != sum(expected_quotas.values()):
        raise ValueError("question count does not match the frozen quota")
    indexed = (
        {row.question_id: row for row in queries},
        {row.question_id: row for row in specifications},
        {row.question_id: row for row in authoring_records},
    )
    if any(len(mapping) != len(queries) for mapping in indexed):
        raise ValueError("question identities must be unique")
    if len({frozenset(mapping) for mapping in indexed}) != 1:
        raise ValueError("query, specification, and authoring identities differ")
    query_by_id, specification_by_id, authoring_by_id = indexed
    manual_by_question = {row.question_id: row for row in manual_searches}
    if len(manual_by_question) != len(manual_searches):
        raise ValueError("manual-search question identities must be unique")

    actual_quotas = Counter(
        (row.domain, row.construction_category) for row in queries
    )
    if any(actual_quotas[key] != value for key, value in expected_quotas.items()):
        raise ValueError("question categories do not match the frozen quota")
    normalized = [normalize_question_text(row.query_text) for row in queries]
    if len(set(normalized)) != len(normalized):
        raise ValueError("question text must be unique after normalization")

    for question_id in sorted(query_by_id):
        query = query_by_id[question_id]
        specification = specification_by_id[question_id]
        authoring = authoring_by_id[question_id]
        if (
            specification.specification_id != authoring.specification_id
            or query.domain != authoring.domain
            or query.construction_category != authoring.construction_category
        ):
            raise ValueError(f"cross-record identity mismatch: {question_id}")
        if authoring.review_decision != ReviewDecision.ACCEPT:
            raise ValueError(f"question is not accepted: {question_id}")
        if authoring.prior_question_check != PriorQuestionCheck.CLEAR:
            raise ValueError(f"prior-question check is not clear: {question_id}")
        if not authoring.source_resolution_checked:
            raise ValueError(f"source resolution is incomplete: {question_id}")
        if query.construction_category == ConstructionCategory.EVIDENCE_INSUFFICIENT:
            search = manual_by_question.get(question_id)
            if (
                search is None
                or search.manual_search_id != authoring.manual_search_record_id
                or search.conclusion != SearchConclusion.CORPUS_INSUFFICIENT
                or search.evidence_found
            ):
                raise ValueError(
                    f"insufficiency candidate lacks a negative manual search: {question_id}"
                )


def freeze_queries(
    destination: Path,
    *,
    batch_id: str,
    queries: Sequence[QueryRecord],
    specifications: Sequence[EvidenceSpecification],
    authoring_records: Sequence[AuthoringRecord],
    manual_searches: Sequence[ManualSearchRecord],
    protocol_path: Path,
    configuration_paths: Mapping[str, Path],
    corpus_hashes: Mapping[Domain | str, Hash],
    prior_inventory_paths: Mapping[str, Path],
    frozen_at: datetime,
    expected_quotas: Mapping[
        tuple[Domain, ConstructionCategory], int
    ] = PREFREEZE_QUESTION_QUOTAS,
) -> FrozenBatchManifest:
    """Validate and atomically write one content-addressed, no-overwrite freeze."""
    if frozen_at.utcoffset() is None:
        raise ValueError("frozen_at must include a timezone")
    _validate_freeze_inputs(
        queries,
        specifications,
        authoring_records,
        manual_searches,
        expected_quotas,
    )
    normalized_corpus_hashes = {
        (key.value if isinstance(key, Domain) else str(key)): value
        for key, value in corpus_hashes.items()
    }
    if set(normalized_corpus_hashes) != {domain.value for domain in Domain}:
        raise ValueError("corpus_hashes must contain both frozen domains")

    rows = {
        "queries": _model_rows(queries, "question_id"),
        "evidence-specifications": _model_rows(
            specifications, "question_id"
        ),
        "authoring-records": _model_rows(authoring_records, "question_id"),
        "manual-search-records": _model_rows(
            manual_searches, "question_id"
        ),
    }
    serialized_rows = {
        name: _canonical_bytes(payload) for name, payload in rows.items()
    }
    record_hashes = {
        f"{name}.json": _sha256_bytes(value)
        for name, value in serialized_rows.items()
    }
    configuration_hashes = {
        name: _sha256_file(path)
        for name, path in sorted(configuration_paths.items())
    }
    prior_inventory_hashes = {
        name: _sha256_file(path)
        for name, path in sorted(prior_inventory_paths.items())
    }
    identity = {
        "batch_id": batch_id,
        "configuration_hashes": configuration_hashes,
        "corpus_hashes": normalized_corpus_hashes,
        "prior_inventory_hashes": prior_inventory_hashes,
        "protocol_hash": _sha256_file(protocol_path),
        "question_ids": sorted(row.question_id for row in queries),
        "record_hashes": record_hashes,
    }
    manifest = FrozenBatchManifest(
        batch_id=batch_id,
        frozen_at=frozen_at,
        question_count=len(queries),
        question_ids=identity["question_ids"],
        record_hashes=record_hashes,
        protocol_hash=identity["protocol_hash"],
        configuration_hashes=configuration_hashes,
        corpus_hashes=normalized_corpus_hashes,
        prior_inventory_hashes=prior_inventory_hashes,
        batch_hash=_sha256_bytes(_canonical_bytes(identity)),
    )
    manifest_bytes = _canonical_bytes(manifest.model_dump(mode="json"))
    existing_manifest = destination / "freeze-manifest.json"
    if destination.exists():
        if existing_manifest.is_file() and existing_manifest.read_bytes() == manifest_bytes:
            return manifest
        raise FileExistsError(f"refusing to overwrite frozen batch: {destination}")

    staging = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        staging.mkdir(parents=True)
        for name, value in serialized_rows.items():
            (staging / f"{name}.json").write_bytes(value)
        (staging / "freeze-manifest.json").write_bytes(manifest_bytes)
        staging.replace(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest


def append_correction(
    ledger_path: Path,
    *,
    previous: FrozenBatchManifest,
    replacement: FrozenBatchManifest,
    changed_question_ids: Sequence[str],
    reason: str,
    corrected_by: str,
    corrected_at: datetime,
    invalidated_run_hashes: Mapping[str, Hash],
) -> CorrectionLedgerEntry:
    """Append a hash-chained correction without changing either frozen batch."""
    if previous.batch_id == replacement.batch_id:
        raise ValueError("replacement must use a new batch_id")
    entries: list[dict[str, Any]] = []
    if ledger_path.exists():
        entries = json.loads(ledger_path.read_text(encoding="utf-8"))
        expected_previous_hash = None
        for raw_entry in entries:
            validated = CorrectionLedgerEntry.model_validate(raw_entry)
            content = validated.model_dump(mode="json")
            recorded_hash = content.pop("entry_hash")
            if content["previous_entry_hash"] != expected_previous_hash:
                raise ValueError("correction ledger hash chain is broken")
            if _sha256_bytes(_canonical_bytes(content)) != recorded_hash:
                raise ValueError("correction ledger entry hash is invalid")
            expected_previous_hash = recorded_hash
    previous_entry_hash = entries[-1]["entry_hash"] if entries else None
    payload = {
        "schema_version": "1.0",
        "correction_id": f"CORRECTION-{len(entries) + 1:03d}",
        "previous_batch_id": previous.batch_id,
        "previous_batch_hash": previous.batch_hash,
        "replacement_batch_id": replacement.batch_id,
        "replacement_batch_hash": replacement.batch_hash,
        "changed_question_ids": sorted(set(changed_question_ids)),
        "reason": reason,
        "corrected_by": corrected_by,
        "corrected_at": corrected_at.isoformat(),
        "invalidated_run_hashes": dict(sorted(invalidated_run_hashes.items())),
        "previous_entry_hash": previous_entry_hash,
    }
    entry = CorrectionLedgerEntry(
        **payload,
        entry_hash=_sha256_bytes(_canonical_bytes(payload)),
    )
    entries.append(entry.model_dump(mode="json"))
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = ledger_path.with_suffix(".tmp")
    temporary.write_bytes(_canonical_bytes(entries))
    temporary.replace(ledger_path)
    return entry
