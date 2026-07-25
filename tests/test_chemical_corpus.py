import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from evidence_routing.chemical_corpus import (
    SCOPE_COLUMNS,
    export_scope_candidates,
    fingerprint_rows,
    freeze_scope_review,
    generate_chemical_corpus_fingerprint,
)


class _Record(dict):
    def data(self):
        return dict(self)


class _Result:
    def __init__(self, rows):
        self.rows = [_Record(row) for row in rows]

    def __iter__(self):
        return iter(self.rows)

    def data(self):
        return [row.data() for row in self.rows]


class _FingerprintSession:
    def __init__(self):
        self.queries = []

    def run(self, query, **_parameters):
        self.queries.append(" ".join(query.split()))
        if "count(standard) AS standard_count" in query:
            return _Result(
                [
                    {
                        "standard_count": 1,
                        "section_count": 2,
                        "stable_id_present": 2,
                        "stable_id_count": 2,
                    }
                ]
            )
        if "SHOW FULLTEXT INDEXES" in query:
            return _Result(
                [
                    {
                        "name": "section_fulltext_cjk",
                        "state": "ONLINE",
                        "labelsOrTypes": ["Section"],
                        "properties": ["title", "summary", "content"],
                        "options": {"indexConfig": {"analyzer": "cjk"}},
                    }
                ]
            )
        if "MATCH (standard:Standard)" in query and "standard.standard_id" in query:
            return _Result([{"uid": "STD1", "standard_id": "GB/T 1", "title": "标准"}])
        if "MATCH (section:Section)" in query and "section.doc_id" in query:
            return _Result(
                [
                    {"uid": "S1", "standard_uid": "STD1", "title": "甲", "content": "A"},
                    {"uid": "S2", "standard_uid": "STD1", "title": "乙", "content": "B"},
                ]
            )
        if "CITES|DEPENDS_ON" in query:
            return _Result(
                [
                    {
                        "source_uid": "S1",
                        "relation_type": "CITES",
                        "target_uid": "S2",
                        "confidence": 0.9,
                    }
                ]
            )
        if "HAS_SUBSECTION" in query:
            return _Result([{"parent_uid": "S1", "child_uid": "S2"}])
        if "HAS_TABLE" in query:
            return _Result([{"section_uid": "S2", "title": "表1", "description": "值"}])
        raise AssertionError(query)


class _ScopeSession:
    def run(self, query, **_parameters):
        assert "properties(standard)" in query
        return _Result(
            [
                {
                    "standard_uid": "STD1",
                    "properties": {
                        "standard_id": "GB/T 1",
                        "title": "危险化学品储存",
                        "status": "active",
                        "section_count": 12,
                    },
                },
                {
                    "standard_uid": "STD2",
                    "properties": {
                        "standard_id": "GB/T 2",
                        "title": "普通纸张",
                        "section_count": 4,
                    },
                },
            ]
        )


def test_fingerprint_rows_is_deterministic_and_order_sensitive():
    rows = [{"uid": "a", "content": "甲"}, {"uid": "b", "content": "乙"}]
    first = fingerprint_rows(rows)
    second = fingerprint_rows(rows)
    reverse = fingerprint_rows(reversed(rows))
    assert first == second
    assert first.sha256 != reverse.sha256
    assert first.record_count == 2


def test_generate_strong_fingerprint_covers_frozen_path_components():
    session = _FingerprintSession()
    fixed_time = datetime(2026, 7, 25, tzinfo=UTC)
    first = generate_chemical_corpus_fingerprint(
        session, source_revision="fixture-v1", created_at=fixed_time
    )
    second = generate_chemical_corpus_fingerprint(
        _FingerprintSession(), source_revision="fixture-v1", created_at=fixed_time
    )
    assert first.corpus_hash == second.corpus_hash
    assert first.section_count == 2
    assert set(first.components) == {
        "standards",
        "sections",
        "graph_edges",
        "hierarchy_edges",
        "tables",
    }
    assert any("ORDER BY uid" in query for query in session.queries)


def test_candidate_export_does_not_make_human_decisions(tmp_path: Path):
    output = tmp_path / "review.csv"
    summary = export_scope_candidates(
        _ScopeSession(),
        terms=["危险化学品", "储存"],
        output_path=output,
    )
    with output.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert summary["inventory_count"] == 2
    assert summary["candidate_count"] == 1
    assert rows[0]["standard_uid"] == "STD1"
    assert rows[0]["decision"] == ""
    assert rows[0]["matched_terms"] == "储存|危险化学品"


def _write_review(path: Path, decision: str = "include") -> None:
    row = dict.fromkeys(SCOPE_COLUMNS, "")
    row.update(
        {
            "standard_uid": "STD1",
            "standard_id": "GB/T 1",
            "title": "虚构危险化学品储存",
            "section_count": "12",
            "matched_terms": "危险化学品",
            "decision": decision,
            "inclusion_reason": "direct scope" if decision == "include" else "",
            "exclusion_reason": "outside scope" if decision == "exclude" else "",
            "reviewer": "reviewer_a",
            "reviewed_at": "2026-07-25",
        }
    )
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCOPE_COLUMNS)
        writer.writeheader()
        writer.writerow(row)


def test_freeze_scope_validates_and_writes_allowlist(tmp_path: Path):
    review = tmp_path / "review.csv"
    output = tmp_path / "scope.json"
    _write_review(review)
    scope = freeze_scope_review(
        review,
        corpus_hash="a" * 64,
        terms=["危险化学品"],
        output_path=output,
        frozen_at=datetime(2026, 7, 25, tzinfo=UTC),
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert scope.included_standard_uids == ("STD1",)
    assert payload["included_standard_count"] == 1
    assert payload["corpus_hash"] == "a" * 64


def test_freeze_scope_rejects_incomplete_review(tmp_path: Path):
    review = tmp_path / "review.csv"
    output = tmp_path / "scope.json"
    _write_review(review)
    rows = review.read_text(encoding="utf-8-sig").replace("reviewer_a", "")
    review.write_text(rows, encoding="utf-8-sig")
    with pytest.raises(ValueError, match="reviewer is required"):
        freeze_scope_review(
            review,
            corpus_hash="a" * 64,
            terms=["危险化学品"],
            output_path=output,
        )
