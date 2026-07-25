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

Phases 1 through 4 are implemented: the repository boundary, frozen Pilot
protocol, schemas, two read-only domain adapters, deterministic BM25 contract,
immutable result cache, six fixed evidence paths, and their command boundary
are in place. The pharmaceutical adapter has passed a live six-path check
against the frozen 2,478-chunk snapshot. The chemical adapter has passed live
six-path and positive graph-expansion checks against the 9,206-standard,
991,453-Section Neo4j instance, using globally unique `Section.uid` values.
The frozen Qwen3-Reranker-0.6B snapshot passed identity verification and real
GPU inference.
The chemical corpus has been strongly fingerprinted. A reproducible title-based
screen produced 532 standards for human review; the completed review froze 399
standards into the chemical question-source allowlist and excluded 133. No
Pilot questions, path labels, or model results have been created.

- [Frozen Pilot design](docs/superpowers/specs/2026-07-23-pilot-first-evidence-routing-design.md)
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

Chemical corpus fingerprinting, human-reviewed scope freezing, and six-path
execution are operational. Commands for annotation, modeling, and evaluation
remain phase-gated until their implementation tasks are completed.

## Publication scope

This is a bounded Pilot study. It does not claim general multi-hop reasoning, generated-answer correctness, or universal cross-domain generalization. Full-dataset expansion occurs only if the frozen Go/No-Go rules support it.
