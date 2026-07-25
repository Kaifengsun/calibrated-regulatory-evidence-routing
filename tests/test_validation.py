import json
from pathlib import Path

import pytest

from evidence_routing.schemas import (
    ConstructionCategory,
    Domain,
    EvidenceSpecification,
    ExperimentManifest,
    PathRun,
    QueryRecord,
)
from evidence_routing.validation import (
    FROZEN_QUESTION_QUOTAS,
    DatasetValidationError,
    validate_dataset,
    validate_manifest,
    validate_path_run,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "data" / "templates"


def _load(name: str) -> dict:
    return json.loads((TEMPLATES / name).read_text(encoding="utf-8"))


def test_duplicate_ranked_evidence_is_rejected_with_stable_code() -> None:
    payload = _load("path-run.example.json")
    duplicate = dict(payload["ranked_units"][0])
    duplicate["rank"] = 2
    payload["ranked_units"].append(duplicate)
    run = PathRun.model_validate(payload)
    with pytest.raises(DatasetValidationError) as captured:
        validate_path_run(run)
    assert [issue.code for issue in captured.value.issues] == ["E_EVIDENCE_ID_DUPLICATE"]


def test_nonconsecutive_rank_is_rejected_with_stable_code() -> None:
    payload = _load("path-run.example.json")
    payload["ranked_units"][0]["rank"] = 2
    run = PathRun.model_validate(payload)
    with pytest.raises(DatasetValidationError) as captured:
        validate_path_run(run)
    assert [issue.code for issue in captured.value.issues] == ["E_RANK_SEQUENCE"]


def test_query_specification_identity_mismatch_is_rejected() -> None:
    query = QueryRecord.model_validate(_load("query-record.example.json"))
    payload = _load("evidence-specification.example.json")
    payload["question_id"] = "CHEM-PILOT-999"
    specification = EvidenceSpecification.model_validate(payload)
    with pytest.raises(DatasetValidationError) as captured:
        validate_dataset([query], [specification], require_frozen_counts=False)
    assert [issue.code for issue in captured.value.issues] == ["E_QUERY_SPEC_MISMATCH"]


def _frozen_dataset() -> tuple[list[QueryRecord], list[EvidenceSpecification]]:
    queries: list[QueryRecord] = []
    specifications: list[EvidenceSpecification] = []
    for (domain, category), count in FROZEN_QUESTION_QUOTAS.items():
        prefix = "CHEM" if domain == Domain.CHEMICAL else "PHARMA"
        language = "zh" if domain == Domain.CHEMICAL else "en"
        for index in range(1, count + 1):
            question_id = f"{prefix}-{category.value.upper()}-{index:03d}"
            source_id = f"SOURCE-{question_id}"
            queries.append(
                QueryRecord(
                    question_id=question_id,
                    domain=domain,
                    language=language,
                    query_text=f"Valid frozen question {question_id}",
                    construction_category=category,
                    source_group_id=f"GROUP-{question_id}",
                    authoring_source_ids=[] if count == 0 else [source_id],
                )
            )
            insufficient = category == ConstructionCategory.EVIDENCE_INSUFFICIENT
            specifications.append(
                EvidenceSpecification(
                    question_id=question_id,
                    specification_id=f"SPEC-{question_id}",
                    sufficient_source_ids=[] if insufficient else [source_id],
                    insufficiency_candidate=insufficient,
                    evidence_scope_note="Frozen quota validation fixture.",
                )
            )
    return queries, specifications


def test_frozen_dataset_accepts_domain_available_quotas() -> None:
    queries, specifications = _frozen_dataset()
    validate_dataset(queries, specifications)


def test_pharmaceutical_citation_question_is_rejected_by_quota() -> None:
    queries, specifications = _frozen_dataset()
    index = next(
        index
        for index, row in enumerate(queries)
        if row.domain == Domain.PHARMACEUTICAL
        and row.construction_category == ConstructionCategory.DIRECT_CLAUSE
    )
    queries[index] = queries[index].model_copy(
        update={"construction_category": ConstructionCategory.CITATION_DEPENDENCY}
    )
    with pytest.raises(DatasetValidationError) as captured:
        validate_dataset(queries, specifications)
    messages = [
        issue.message
        for issue in captured.value.issues
        if issue.code == "E_CATEGORY_QUOTA"
    ]
    assert any(
        "domain=pharmaceutical; category=citation_dependency; expected=0; actual=1"
        in message
        for message in messages
    )


def test_manifest_requires_input_and_configuration_hashes() -> None:
    payload = _load("experiment-manifest.example.json")
    payload["input_hashes"] = {}
    manifest = ExperimentManifest.model_validate(payload)
    with pytest.raises(DatasetValidationError) as captured:
        validate_manifest(manifest)
    assert [issue.code for issue in captured.value.issues] == ["E_INPUT_HASH_MISSING"]
