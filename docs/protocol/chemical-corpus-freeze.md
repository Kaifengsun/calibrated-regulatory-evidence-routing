# Chemical Corpus Fingerprint and Scope Freeze

Status: implementation protocol for the end-to-end Pilot.

## Frozen population

The chemical retrieval population is the complete read-only Neo4j database:
9,206 `Standard` nodes and approximately 991,000 `Section` nodes at the
observed snapshot. BM25 is not filtered to the chemical-safety allowlist.

The 60 chemical Pilot questions and their gold evidence may only be constructed
from standards included in a separately frozen, human-reviewed allowlist.
Results outside that allowlist remain eligible retrieval results and are
labelled `IRRELEVANT` or `HARMFUL` according to the annotation protocol. They
are not automatically harmful.

## Strong corpus fingerprint

`chemical-fingerprint` streams deterministic, ordered records from Neo4j. It
hashes only canonical JSON lines in memory and writes no source text. The
fingerprint covers:

1. Standard identifiers and scope-relevant metadata;
2. Section identifiers, document linkage, BM25 text fields, and structural
   fields;
3. `CITES` and `DEPENDS_ON` targets and confidence;
4. `HAS_SUBSECTION` hierarchy;
5. directly attached table titles and descriptions;
6. the `section_fulltext_cjk` index definition.

The component digests and metadata are combined into one corpus SHA-256.
Generation fails if `Section.uid` is missing or non-unique, if the full-text
index is not online, or if node counts change during the component scans.

The fingerprint command is intentionally read-only. A complete scan of the
large Section collection can take several minutes.

## Candidate generation

`configs/chemical-scope-v1.yaml` contains high-specificity screening terms. A
term is matched as a substring of the whitespace-normalized Standard title. A
match only places a Standard into the review CSV; it never includes that
Standard in the allowlist. The deliberately narrow title rule keeps the manual
review workload bounded and makes candidate generation easy to reproduce.

The screening rules must be frozen before reviewing candidates. Their SHA-256
is stored in the final scope manifest.

## Human review

Every exported candidate must receive exactly one decision:

- `include`: directly relevant to chemical safety and accompanied by an
  inclusion reason;
- `exclude`: outside the intended question-source scope and accompanied by an
  exclusion reason.

Both decisions require a reviewer identifier and review date. The validator
rejects blank decisions, duplicate Standard identifiers, missing reasons, and
an empty allowlist. The completed review CSV is private working data. The
frozen JSON manifest binds the sorted decisions to the corpus hash and
screening-rule hash.

The allowlist must be frozen before formal Pilot question construction and
must not be revised in response to retrieval performance.

Freezing is idempotent. Re-running the command with the same corpus, screening
rules, and reviewed decisions preserves the original manifest and timestamp.
The command refuses to overwrite an existing frozen manifest when any identity
field differs.

## Local commands

The ignored `configs/local.yaml` must reference environment-variable names for
the Neo4j connection. No credential value is written by these commands.

```powershell
evidence-routing chemical-fingerprint `
  --config configs/local.yaml `
  --source-revision chemical-neo4j-pilot-v1 `
  --output artifacts/private/chemical-corpus-fingerprint.json

evidence-routing chemical-export-scope `
  --config configs/local.yaml `
  --scope-config configs/chemical-scope-v1.yaml `
  --output artifacts/private/chemical-standard-scope-review.csv

evidence-routing chemical-freeze-scope `
  --review artifacts/private/chemical-standard-scope-review.csv `
  --fingerprint artifacts/private/chemical-corpus-fingerprint.json `
  --scope-config configs/chemical-scope-v1.yaml `
  --output artifacts/private/chemical-standard-scope-frozen.json
```
