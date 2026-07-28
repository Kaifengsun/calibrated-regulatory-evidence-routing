---
goal: Clean and Clarify the Completed Pilot Repository
version: 1.0
date_created: 2026-07-28
last_updated: 2026-07-28
owner: Kaifeng Sun
status: 'Completed'
tags: [refactor, cleanup, reproducibility, manuscript]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

Remove regenerated local artifacts and the superseded Word manuscript while
preserving all code, frozen research evidence, and public reproducibility
materials.

## 1. Requirements & Constraints

- **REQ-001**: Retain `output/word/When_Does_Evidence_Expansion_Help_Revised.docx`.
- **REQ-002**: Retain all tracked source code, tests, manifests, protocols, plans, figures, and tables.
- **SEC-001**: Retain ignored `artifacts/private/` and `configs/local.yaml`; do not stage or publish them.
- **CON-001**: Delete only explicitly enumerated regenerated or superseded paths.
- **CON-002**: Do not use broad ignored-file cleanup commands without exact path restrictions.
- **GUD-001**: Update public documentation to describe the completed Pilot and current manuscript.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Remove regenerated and superseded artifacts.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Delete enumerated DOCX QA, LibreOffice temporary, Python cache, package metadata, and `tmp/` directories. | Yes | 2026-07-28 |
| TASK-002 | Remove tracked `output/word/When_Does_Evidence_Expansion_Help.docx`; preserve the revised manuscript and Git history. | Yes | 2026-07-28 |

### Implementation Phase 2

- GOAL-002: Align repository documentation and ignore rules with the completed Pilot.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Update `README.md` status, results, manuscript links, and validation commands. | Yes | 2026-07-28 |
| TASK-004 | Update `.gitignore` for Word lock files and DOCX QA/LibreOffice temporary directories. | Yes | 2026-07-28 |
| TASK-005 | Update the historical manuscript plan to identify the revised DOCX as the retained final artifact. | Yes | 2026-07-28 |

### Implementation Phase 3

- GOAL-003: Verify cleanup safety and repository health.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Run the complete pytest suite, configuration validation, and privacy validation. | Yes | 2026-07-28 |
| TASK-007 | Verify the revised DOCX exists and Git contains no unexpected staged or untracked private files. | Yes | 2026-07-28 |

## 3. Alternatives

- **ALT-001**: Delete only untracked QA folders. Rejected because the stale README and duplicate tracked manuscript would continue to confuse readers.
- **ALT-002**: Remove historical plans, design specifications, and private evidence. Rejected because those materials support reproducibility and pre-specification claims.
- **ALT-003**: Run `git clean -fdX`. Rejected because it would remove required private evidence and machine-local configuration.

## 4. Dependencies

- **DEP-001**: Git history must contain the superseded DOCX before removal.
- **DEP-002**: The revised DOCX must exist before the older DOCX is removed.
- **DEP-003**: The project Python environment must provide pytest and runtime dependencies.

## 5. Files

- **FILE-001**: `.gitignore` — add generated-document ignore rules.
- **FILE-002**: `README.md` — replace stale phase status with completed Pilot status.
- **FILE-003**: `plan/process-diagnostic-manuscript-1.md` — mark the older filename as superseded.
- **FILE-004**: `output/word/When_Does_Evidence_Expansion_Help.docx` — remove superseded tracked manuscript.
- **FILE-005**: `output/word/When_Does_Evidence_Expansion_Help_Revised.docx` — retain authoritative manuscript.

## 6. Testing

- **TEST-001**: `pytest -q` exits successfully.
- **TEST-002**: Example configuration validation exits successfully.
- **TEST-003**: Repository privacy validation exits successfully.
- **TEST-004**: `git status --short` contains no unexpected files after cleanup.

## 7. Risks & Assumptions

- **RISK-001**: A broad ignored-file deletion could destroy private annotation evidence; use exact paths only.
- **RISK-002**: Removing research plans could weaken the pre-specification record; retain them.
- **ASSUMPTION-001**: The revised DOCX is the sole current manuscript submitted for project-group evaluation.
- **ASSUMPTION-002**: QA renders, caches, and LibreOffice profiles are reproducible and contain no unique research data.

## 8. Related Specifications / Further Reading

- `docs/superpowers/specs/2026-07-28-repository-cleanup-design.md`
- `docs/superpowers/specs/2026-07-27-manuscript-submission-polish-design.md`
- `plan/process-diagnostic-manuscript-1.md`
