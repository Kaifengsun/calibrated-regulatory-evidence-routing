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

Phases 1 through 4 and Pilot question construction are implemented: the repository boundary, frozen Pilot
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
path labels or model results have been created. The complete path-blind
120-question Pilot has been human reviewed and frozen: 60 chemical questions,
60 pharmaceutical questions, 120 accepted authoring records, and 27 documented
negative manual searches. No P0-P5 path was run before this freeze.
After the freeze, all six paths were executed for every question. The resulting
720 path runs are complete with no execution errors and are bound to the frozen
question-batch hash. Primary method-blinded annotation is complete: all six
private 20-question workbooks passed immutable-field and label validation, and
their 3,446 displayed evidence rows were expanded into 10,385 annotations with
exact coverage of every ranked item and context sidecar in the 720 path runs.
The frozen seed and domain-category quotas selected exactly 30 complete
questions without using evidence labels, and their independent duplicate-review
workbook has been exported and completed. Pre-adjudication agreement is 71.5%
(question-cluster bootstrap 95% CI 66.1%-76.9%) with Cohen's kappa 0.556
(95% CI 0.470-0.637) across 901 visible evidence rows. The 279 label or
HARMFUL-reason disagreements have been exported for adjudication; final labels
are now frozen. The final private label set contains exactly one label for each
of the 10,385 ranked or sidecar path occurrences; 837 occurrences were resolved
through 279 completed adjudication decisions, while 27 documented negative
manual corpus searches remain bound to evidence-insufficiency questions.

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
