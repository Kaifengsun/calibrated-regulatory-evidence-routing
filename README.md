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

Phases 1 and 2 are complete: the repository boundary, read-only source
inventory, machine-readable Pilot protocol, schemas, safe templates, and
tracked-file privacy checks are in place. Phase 3 will implement the two
read-only domain adapters and deterministic BM25 contract. No Pilot questions,
path labels, or model results have been created.

- [Frozen Pilot design](docs/superpowers/specs/2026-07-23-pilot-first-evidence-routing-design.md)
- [End-to-end Pilot plan](plan/process-end-to-end-pilot-1.md)
- [Source-system inventory](docs/protocol/source-system-inventory.md)
- [Frozen Pilot v1 protocol](docs/protocol/pilot-v1.md)

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

Commands for path execution, annotation, modeling, and evaluation are registered in the CLI but remain phase-gated until their implementation tasks are completed.

## Publication scope

This is a bounded Pilot study. It does not claim general multi-hop reasoning, generated-answer correctness, or universal cross-domain generalization. Full-dataset expansion occurs only if the frozen Go/No-Go rules support it.
