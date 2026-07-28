# Calibrated Regulatory Evidence Routing

Research code and evaluation artifacts for calibrated, query-adaptive evidence routing in cross-domain regulatory retrieval.

## Research question

Starting from a fixed BM25 retrieval result, can a lightweight calibrated router choose the least costly evidence path that retrieves complete attributable evidence, while abstaining when no evaluated path is likely to be sufficient?

The Pilot covers:

- Chinese chemical-safety standards;
- English pharmaceutical regulatory documents;
- six frozen paths combining BM25, one neural reranker, context sidecars, and controlled relation expansion;
- Logistic Regression and XGBoost routing;
- evidence-sufficiency calibration and abstention.

## Current status

The end-to-end Pilot is complete. The frozen study contains 120 reviewed
questions (60 chemical-safety and 60 pharmaceutical-regulatory), six fixed
paths per question, 720 path outputs, and 10,385 final evidence labels. Thirty
complete questions received independent duplicate annotation. Agreement and
adjudication records, grouped out-of-fold routing, calibration-only abstention,
cross-domain transfer, paired uncertainty analysis, and the prespecified
Go/No-Go decision have all been completed.

The main diagnostic result is that structural context supplied the clearest
independent benefit. Reranking and conservative one-hop relation expansion
provided limited independent rescue, and calibration-only abstention did not
reach usable risk and coverage. The prespecified expansion decision was
therefore **NO-GO**. This decision stops full-dataset expansion of the original
calibrated-routing study; it does not invalidate the completed diagnostic
Pilot.

The English diagnostic manuscript is complete and is currently under
project-group evaluation. The repository retains one authoritative Word
manuscript and the aggregate evidence required to reproduce its reported
statistics.

- [Frozen Pilot design](docs/superpowers/specs/2026-07-23-pilot-first-evidence-routing-design.md)
- [Domain-available quota amendment](docs/superpowers/specs/2026-07-25-domain-available-category-quotas-amendment-design.md)
- [Six frozen evidence paths design](docs/superpowers/specs/2026-07-25-six-frozen-evidence-paths-design.md)
- [End-to-end Pilot plan](plan/process-end-to-end-pilot-1.md)
- [Source-system inventory](docs/protocol/source-system-inventory.md)
- [Frozen Pilot v1 protocol](docs/protocol/pilot-v1.md)
- [Chemical corpus fingerprint and scope freeze](docs/protocol/chemical-corpus-freeze.md)
- [Question construction guide](docs/annotation/question-construction-v1.md)
- [Evidence labeling guide](docs/annotation/evidence-labeling-v1.md)
- [Twenty-question authoring plan](plan/process-pilot-question-authoring-1.md)
- [Frozen chemical corpus manifest](data/manifests/chemical-corpus-pilot-v1.json)
- [Frozen pharmaceutical corpus manifest](data/manifests/pharmaceutical-corpus-pilot-v1.json)
- [Chemical scope-screening manifest](data/manifests/chemical-scope-screening-v1.json)
- [Frozen chemical scope summary](data/manifests/chemical-scope-freeze-v1.json)
- [Frozen 120-question Pilot summary](data/manifests/pilot-120-question-freeze-v1.json)
- [Complete 720-run path summary](data/manifests/pilot-120-path-run-v1.json)
- [Primary annotation export summary](data/manifests/pilot-120-primary-annotation-export-v1.json)
- [Primary annotation import summary](data/manifests/pilot-120-primary-annotation-import-v1.json)
- [Duplicate-question selection summary](data/manifests/pilot-120-duplicate-selection-v1.json)
- [Pre-adjudication agreement summary](data/manifests/pilot-120-agreement-pre-adjudication-v1.json)
- [Final annotation freeze summary](data/manifests/pilot-120-annotation-freeze-v1.json)
- [Pilot feasibility report](docs/results/pilot-v1-feasibility-report.md)
- [Diagnostic manuscript source](manuscript/manuscript.md)
- [Current Word manuscript](output/word/When_Does_Evidence_Expansion_Help_Revised.docx)

## Repository boundary

This repository may contain original code, schemas, safe templates, protocol hashes, aggregate results, and redistribution-safe metadata. It must not contain copyrighted source corpora, database snapshots, credentials, machine-local paths, or private review workbooks.

Local source systems are referenced through environment variables and an ignored `configs/local.yaml`. Start from `configs/local.example.yaml`.

## Development

Requirements:

- Python 3.11 or later
- Git

Install the package in editable mode:

```powershell
python -m pip install -e ".[dev]"
```

Run the current checks:

```powershell
pytest
python -m evidence_routing.cli validate-config --config configs/local.example.yaml
python -m evidence_routing.privacy
```

The frozen Pilot has completed all annotation, modeling, evaluation, and
reporting phases. Re-running live retrieval requires the ignored local source
systems and configuration; aggregate manuscript results can be checked from
the committed manifests, tables, and tests.

## Publication scope

This is a bounded Pilot study. It does not claim general multi-hop reasoning, generated-answer correctness, or universal cross-domain generalization. Full-dataset expansion occurs only if the frozen Go/No-Go rules support it.
