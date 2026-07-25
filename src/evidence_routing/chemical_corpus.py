"""Reproducible fingerprinting and human-reviewed scope control for Neo4j."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

FINGERPRINT_SCHEMA_VERSION = "1.0"
SCOPE_SCHEMA_VERSION = "1.0"

_STANDARD_ID_KEYS = ("standard_id", "standard_number", "standard_no", "uid")
_TITLE_KEYS = ("title", "chinese_name", "name", "standard_name")
_STATUS_KEYS = ("status", "standard_status", "validity")
_CATEGORY_KEYS = ("standard_category", "category", "classification", "ccs")
SCOPE_COLUMNS = (
    "standard_uid",
    "standard_id",
    "title",
    "status",
    "category",
    "section_count",
    "matched_terms",
    "decision",
    "inclusion_reason",
    "exclusion_reason",
    "reviewer",
    "reviewed_at",
)


class _Record(Protocol):
    def data(self) -> dict[str, Any]: ...


class _Result(Protocol):
    def __iter__(self) -> Iterable[_Record]: ...

    def data(self) -> list[dict[str, Any]]: ...


class _Session(Protocol):
    def run(self, query: str, **parameters: Any) -> _Result: ...


@dataclass(frozen=True, slots=True)
class FingerprintComponent:
    record_count: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ChemicalCorpusFingerprint:
    schema_version: str
    algorithm: str
    corpus_hash: str
    source_revision: str
    created_at: str
    standard_count: int
    section_count: int
    components: dict[str, FingerprintComponent]
    fulltext_index: list[dict[str, Any]]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FrozenChemicalScope:
    schema_version: str
    corpus_hash: str
    candidate_rules_hash: str
    review_hash: str
    included_standard_count: int
    excluded_candidate_count: int
    included_standard_uids: tuple[str, ...]
    frozen_at: str

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


_COMPONENT_QUERIES: dict[str, str] = {
    "standards": """
        MATCH (standard:Standard)
        RETURN standard.uid AS uid,
               standard.standard_id AS standard_id,
               standard.title AS title,
               standard.chinese_name AS chinese_name,
               standard.name AS name,
               standard.status AS status,
               standard.standard_category AS standard_category,
               standard.category AS category,
               standard.keywords AS keywords,
               standard.entities AS entities,
               standard.industry AS industry,
               standard.summary AS summary,
               standard.full_summary AS full_summary,
               standard.applicable_scope AS applicable_scope,
               standard.main_content AS main_content,
               standard.significance AS significance,
               standard.key_info AS key_info
        ORDER BY uid
    """,
    "sections": """
        MATCH (section:Section)
        RETURN section.uid AS uid,
               section.standard_uid AS standard_uid,
               section.doc_id AS doc_id,
               section.raw_standard_id AS raw_standard_id,
               section.section_number AS section_number,
               section.title AS title,
               section.summary AS summary,
               section.content AS content,
               section.path AS path,
               section.parent_doc_id AS parent_doc_id
        ORDER BY uid
    """,
    "graph_edges": """
        MATCH (source:Section)-[relation:CITES|DEPENDS_ON]->(target:Section)
        RETURN source.uid AS source_uid,
               type(relation) AS relation_type,
               target.uid AS target_uid,
               relation.confidence AS confidence
        ORDER BY source_uid, relation_type, target_uid, confidence
    """,
    "hierarchy_edges": """
        MATCH (parent:Section)-[:HAS_SUBSECTION]->(child:Section)
        RETURN parent.uid AS parent_uid, child.uid AS child_uid
        ORDER BY parent_uid, child_uid
    """,
    "tables": """
        MATCH (section:Section)-[:HAS_TABLE]->(table:Table)
        RETURN section.uid AS section_uid,
               table.title AS title,
               table.description AS description
        ORDER BY section_uid, title, description
    """,
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _record_payload(record: Any) -> dict[str, Any]:
    if isinstance(record, Mapping):
        return dict(record)
    if hasattr(record, "data"):
        return dict(record.data())
    return dict(record)


def fingerprint_rows(rows: Iterable[Any]) -> FingerprintComponent:
    """Hash a deterministically ordered record stream without retaining its text."""
    digest = hashlib.sha256()
    count = 0
    for record in rows:
        digest.update(_canonical_bytes(_record_payload(record)))
        digest.update(b"\n")
        count += 1
    return FingerprintComponent(record_count=count, sha256=digest.hexdigest())


def generate_chemical_corpus_fingerprint(
    session: _Session,
    *,
    source_revision: str,
    created_at: datetime | None = None,
) -> ChemicalCorpusFingerprint:
    """Generate a strong fingerprint over every field used by the frozen paths."""
    if not source_revision.strip():
        raise ValueError("source_revision must be non-empty")
    counts = session.run(
        """
        MATCH (standard:Standard)
        WITH count(standard) AS standard_count
        MATCH (section:Section)
        RETURN standard_count,
               count(section) AS section_count,
               count(section.uid) AS stable_id_present,
               count(DISTINCT section.uid) AS stable_id_count
        """
    ).data()
    if len(counts) != 1:
        raise RuntimeError("corpus count query did not return exactly one row")
    summary = counts[0]
    section_count = int(summary["section_count"])
    if (
        section_count <= 0
        or int(summary["stable_id_present"]) != section_count
        or int(summary["stable_id_count"]) != section_count
    ):
        raise RuntimeError("every Section must have a globally unique uid")

    components = {
        name: fingerprint_rows(session.run(query))
        for name, query in _COMPONENT_QUERIES.items()
    }
    if components["standards"].record_count != int(summary["standard_count"]):
        raise RuntimeError("Standard count changed while the fingerprint was generated")
    if components["sections"].record_count != section_count:
        raise RuntimeError("Section count changed while the fingerprint was generated")

    index_rows = session.run(
        """
        SHOW FULLTEXT INDEXES YIELD name, state, labelsOrTypes, properties, options
        WHERE name = 'section_fulltext_cjk'
        RETURN name, state, labelsOrTypes, properties, options
        ORDER BY name
        """
    ).data()
    if len(index_rows) != 1 or index_rows[0].get("state") != "ONLINE":
        raise RuntimeError("section_fulltext_cjk must exist and be ONLINE")
    index_payload = [_record_payload(row) for row in index_rows]

    identity = {
        "schema_version": FINGERPRINT_SCHEMA_VERSION,
        "algorithm": "sha256-canonical-jsonl-v1",
        "source_revision": source_revision.strip(),
        "standard_count": int(summary["standard_count"]),
        "section_count": section_count,
        "components": {name: asdict(value) for name, value in components.items()},
        "fulltext_index": index_payload,
    }
    corpus_hash = hashlib.sha256(_canonical_bytes(identity)).hexdigest()
    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC).isoformat()
    return ChemicalCorpusFingerprint(
        schema_version=FINGERPRINT_SCHEMA_VERSION,
        algorithm="sha256-canonical-jsonl-v1",
        corpus_hash=corpus_hash,
        source_revision=source_revision.strip(),
        created_at=timestamp,
        standard_count=int(summary["standard_count"]),
        section_count=section_count,
        components=components,
        fulltext_index=index_payload,
    )


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Mapping):
        return " ".join(f"{key} {_flatten_text(item)}" for key, item in value.items())
    if isinstance(value, list | tuple | set):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def _first_text(properties: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _flatten_text(properties.get(key)).strip()
        if value:
            return value
    return ""


def candidate_rules_hash(terms: Iterable[str]) -> str:
    normalized = sorted(
        {re.sub(r"\s+", "", term).casefold() for term in terms if term.strip()}
    )
    if not normalized:
        raise ValueError("at least one non-empty candidate term is required")
    rules = {
        "matching": "normalized_standard_title_substring_v1",
        "terms": normalized,
    }
    return hashlib.sha256(_canonical_bytes(rules)).hexdigest()


def export_scope_candidates(
    session: _Session,
    *,
    terms: Iterable[str],
    output_path: Path,
) -> dict[str, Any]:
    """Export keyword-screened standards with blank human decision fields."""
    normalized_terms = sorted({term.strip() for term in terms if term.strip()})
    rules_hash = candidate_rules_hash(normalized_terms)
    rows = session.run(
        """
        MATCH (standard:Standard)
        RETURN standard.uid AS standard_uid,
               properties(standard) AS properties
        ORDER BY standard_uid
        """
    )
    candidates: list[dict[str, str]] = []
    inventory_count = 0
    for record in rows:
        inventory_count += 1
        row = _record_payload(record)
        standard_uid = str(row.get("standard_uid") or "").strip()
        properties = row.get("properties") or {}
        if not standard_uid or not isinstance(properties, Mapping):
            raise RuntimeError("Standard candidate row lacks uid or properties")
        searchable = re.sub(
            r"\s+",
            "",
            _first_text(properties, _TITLE_KEYS),
        ).casefold()
        matched = [
            term
            for term in normalized_terms
            if re.sub(r"\s+", "", term).casefold() in searchable
        ]
        if not matched:
            continue
        candidates.append(
            {
                "standard_uid": standard_uid,
                "standard_id": _first_text(properties, _STANDARD_ID_KEYS),
                "title": _first_text(properties, _TITLE_KEYS),
                "status": _first_text(properties, _STATUS_KEYS),
                "category": _first_text(properties, _CATEGORY_KEYS),
                "section_count": str(int(properties.get("section_count") or 0)),
                "matched_terms": "|".join(matched),
                "decision": "",
                "inclusion_reason": "",
                "exclusion_reason": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCOPE_COLUMNS)
        writer.writeheader()
        writer.writerows(candidates)
    temporary.replace(output_path)
    return {
        "schema_version": SCOPE_SCHEMA_VERSION,
        "inventory_count": inventory_count,
        "candidate_count": len(candidates),
        "candidate_rules_hash": rules_hash,
    }


def freeze_scope_review(
    review_path: Path,
    *,
    corpus_hash: str,
    terms: Iterable[str],
    output_path: Path,
    frozen_at: datetime | None = None,
) -> FrozenChemicalScope:
    """Validate completed human decisions and freeze the included standard IDs."""
    if not re.fullmatch(r"[a-f0-9]{64}", corpus_hash):
        raise ValueError("corpus_hash must be a lowercase SHA-256")
    with review_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != SCOPE_COLUMNS:
            raise ValueError("scope review columns do not match the frozen template")
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    if not rows:
        raise ValueError("scope review contains no candidate standards")

    errors: list[str] = []
    seen: set[str] = set()
    included: list[str] = []
    excluded = 0
    for line_number, row in enumerate(rows, start=2):
        uid = row["standard_uid"]
        decision = row["decision"].lower()
        if not uid:
            errors.append(f"line {line_number}: standard_uid is required")
        elif uid in seen:
            errors.append(f"line {line_number}: duplicate standard_uid {uid!r}")
        seen.add(uid)
        if decision not in {"include", "exclude"}:
            errors.append(f"line {line_number}: decision must be include or exclude")
        if not row["reviewer"]:
            errors.append(f"line {line_number}: reviewer is required")
        if not row["reviewed_at"]:
            errors.append(f"line {line_number}: reviewed_at is required")
        if decision == "include":
            included.append(uid)
            if not row["inclusion_reason"]:
                errors.append(f"line {line_number}: inclusion_reason is required")
        elif decision == "exclude":
            excluded += 1
            if not row["exclusion_reason"]:
                errors.append(f"line {line_number}: exclusion_reason is required")
    if errors:
        preview = "\n".join(errors[:20])
        suffix = "" if len(errors) <= 20 else f"\n... and {len(errors) - 20} more"
        raise ValueError(f"scope review is incomplete:\n{preview}{suffix}")
    if not included:
        raise ValueError("scope review must include at least one standard")

    normalized_rows = sorted(rows, key=lambda row: row["standard_uid"])
    review_hash = hashlib.sha256(_canonical_bytes(normalized_rows)).hexdigest()
    identity = {
        "schema_version": SCOPE_SCHEMA_VERSION,
        "corpus_hash": corpus_hash,
        "candidate_rules_hash": candidate_rules_hash(terms),
        "review_hash": review_hash,
        "included_standard_count": len(included),
        "excluded_candidate_count": excluded,
        "included_standard_uids": tuple(sorted(included)),
    }
    if output_path.exists():
        try:
            existing_payload = json.loads(output_path.read_text(encoding="utf-8"))
            existing = FrozenChemicalScope(
                schema_version=str(existing_payload["schema_version"]),
                corpus_hash=str(existing_payload["corpus_hash"]),
                candidate_rules_hash=str(existing_payload["candidate_rules_hash"]),
                review_hash=str(existing_payload["review_hash"]),
                included_standard_count=int(existing_payload["included_standard_count"]),
                excluded_candidate_count=int(existing_payload["excluded_candidate_count"]),
                included_standard_uids=tuple(existing_payload["included_standard_uids"]),
                frozen_at=str(existing_payload["frozen_at"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise FileExistsError(
                f"refusing to overwrite invalid frozen scope: {output_path}"
            ) from error
        existing_identity = {
            key: getattr(existing, key)
            for key in identity
        }
        if existing_identity != identity:
            raise FileExistsError(
                f"refusing to overwrite frozen scope with different review data: {output_path}"
            )
        return existing

    scope = FrozenChemicalScope(
        **identity,
        frozen_at=(frozen_at or datetime.now(UTC)).astimezone(UTC).isoformat(),
    )
    write_json_atomic(output_path, scope.to_payload())
    return scope
