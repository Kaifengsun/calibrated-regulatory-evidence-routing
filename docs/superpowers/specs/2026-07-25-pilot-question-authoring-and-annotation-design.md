# Pilot Question Authoring and Annotation Design

**Status:** Approved design, locally reviewed written specification
**Date:** 2026-07-25
**Scope:** Twenty-question pre-freeze batch and its review workflow

## 1. Purpose

This phase establishes a reliable question-authoring and evidence-annotation
workflow before constructing the complete 120-question Pilot. It produces 20
review candidates: 10 Chinese chemical-safety questions and 10 English
pharmaceutical-regulatory questions. Each domain contributes exactly two
questions from each of the five frozen construction categories.

The 20 questions are workflow-validation candidates, not automatically part of
the final frozen Pilot. They may enter the final candidate pool only after
human review, evidence verification, prior-question non-overlap checks, and an
explicit freeze decision.

This phase does not train a router, report Pilot performance, build a web
interface, add an LLM judge, or construct all 120 questions.

## 2. Authoring Principle and Leakage Boundary

Question construction is evidence-first but path-blind:

1. inspect frozen source evidence and identify a realistic regulatory
   information need;
2. specify the evidence required for a complete answer;
3. write a natural question without exposing the answer, standard number, or
   clause identifier unnecessarily;
4. complete pre-freeze human review;
5. freeze the question and evidence specification;
6. only then execute `P0` through `P5`.

Authors must not inspect candidate rankings or path outputs before the question
is frozen. A question may not be revised in response to path performance.
Necessary post-freeze corrections must create a new version with an explicit
reason and invalidate the earlier result.

The tracked repository may contain redistribution-safe identifiers, schemas,
templates, aggregate manifests, and guidelines. Source text, private review
workbooks, machine-local paths, and credentials remain in the ignored local
authoring area.

## 3. Batch Composition

The pre-freeze batch contains exactly 20 questions:

| Domain | Language | Questions |
|---|---|---:|
| Chemical safety | Chinese | 10 |
| Pharmaceutical regulation | English | 10 |

Each domain contains exactly two questions in each category:

| Category | Required evidence structure |
|---|---|
| `direct_clause` | One attributable direct clause is sufficient. |
| `parent_heading_context` | Correct interpretation requires a heading, immediate parent, or scope context in addition to the direct unit. |
| `table_related` | Complete evidence requires an eligible existing table-text sidecar; image recognition is outside scope. |
| `citation_dependency` | Complete evidence requires one eligible outgoing `CITES` or `DEPENDS_ON` target. |
| `evidence_insufficient` | The frozen corpus lacks complete evidence, confirmed through a documented manual search. |

The sample is deliberately balanced for workflow verification. It is not used
to estimate the natural prevalence of the five categories.

## 4. Counter-Cue Requirements

The batch must contain non-trivial counter-cue cases so that future routing
cannot be reduced to keyword matching. Across the 20 questions, the authoring
log must include applicable examples of:

- relation wording where a direct clause is nevertheless sufficient;
- no explicit relation wording where a cited or dependent clause is required;
- table wording where the answer is actually in prose;
- a plausible high-ranked result with the wrong object, scope, jurisdiction,
  or regulatory version.

Counter-cue tags describe construction intent. They do not determine the final
path-success labels.

## 5. Candidate Discovery

Candidate discovery is modular and read-only:

- the chemical selector uses only the frozen 399-standard allowlist and the
  frozen Neo4j corpus;
- the pharmaceutical selector uses only the frozen 2,478-chunk snapshot and
  its regulatory evidence graph;
- direct candidates require attributable text and stable source identifiers;
- context candidates require an eligible heading, immediate parent, or table
  sidecar;
- citation candidates require one deterministic outgoing normalized
  `CITES` or `DEPENDS_ON` relation with confidence at least 0.85;
- insufficiency candidates are not created automatically from retrieval
  failure.

Selectors produce candidate evidence structures, not finished questions or
automatic category decisions. A human must confirm that each structure
supports a realistic information need and that the evidence specification is
correct.

## 6. Authoring Records

Every candidate consists of:

- one version-1 `QueryRecord`;
- one version-1 `EvidenceSpecification`;
- a private authoring record containing the minimum source excerpt needed for
  human verification;
- an audit record describing construction rationale, prior-question checks,
  and review status.

For sufficient-single-item questions, `sufficient_source_ids` identifies the
eligible complete evidence. For multi-unit questions,
`required_source_ids` lists every unit required for completeness. An
`evidence_insufficient` candidate has neither invented required evidence nor a
success label; it instead carries a manual negative-search record.

## 7. Pre-Freeze Human Review

The pre-freeze review verifies that:

- the question resembles a realistic information need;
- wording does not unnecessarily reveal the answer or source identifier;
- the specified evidence completely supports the intended answer;
- the proposed category reflects the evidence structure;
- the question does not materially duplicate the evaluation questions used in
  either earlier manuscript;
- the source grouping is correct for later leakage-safe splitting;
- any counter-cue tag is justified.

The review outcome is one of:

- `accept`;
- `revise_and_review`;
- `reject_and_replace`.

Only accepted records can be frozen. Revised records must complete review
again.

## 8. Evidence Annotation

After question freeze and six-path execution, every ranked evidence unit and
eligible context sidecar receives exactly one label:

- `REQUIRED`;
- `SUFFICIENT`;
- `CONTEXT`;
- `IRRELEVANT`;
- `HARMFUL`.

Ordinary noise, duplication, and weak topical relevance are `IRRELEVANT`, not
automatically `HARMFUL`. Harm is assessed in the frozen risk-sensitive order:

1. wrong regulatory document or standard version;
2. wrong regulated object, product, substance, organization, or jurisdiction;
3. wrong scope, responsible party, condition, threshold, or exception;
4. direct conflict with correct evidence;
5. other material likely to alter the regulatory interpretation.

Evidence completeness, harmful expansion, and combined path success remain
separate outputs. Six failed paths never prove corpus insufficiency.

## 9. Review Artifacts

The first batch uses spreadsheet review artifacts rather than a web
application. The pre-freeze workbook contains the question, category,
counter-cue tags, source identifiers, controlled evidence excerpt, evidence
specification, and review decision fields.

The post-freeze annotation workbook contains randomized method-blinded evidence
packages. It preserves immutable hidden identities through a private mapping
file outside version control. Import rejects altered question, path, source,
rank, or sidecar identities.

The reviewer does not need to locate every original source file. Direct source
inspection is required only for ambiguous evidence, adjudication, or a manual
corpus-insufficiency search.

## 10. Validation and Failure Handling

Freezing is blocked when any of the following occurs:

- domain/category counts differ from the approved 2-by-5 design;
- question, specification, source, or evidence identifiers are missing or
  malformed;
- question IDs or normalized question texts are duplicated;
- a source identifier cannot be resolved in the frozen corpus;
- a citation candidate lacks an eligible frozen graph edge;
- a required or sufficient evidence list is internally inconsistent;
- an insufficiency candidate lacks a completed manual-search record;
- a review workbook changes an immutable identity field;
- a question has not received an explicit `accept` decision.

Failures are reported with stable codes and actionable record identifiers. A
partially valid batch is not silently frozen.

## 11. Verification

Fixture tests cover quotas, uniqueness, schema validation, source resolution,
counter-cue records, manual-search requirements, immutable review identities,
and deterministic workbook ordering. Bounded live checks cover candidate
selection in both frozen domains without committing source text.

The phase is successful when:

- two candidate questions can be constructed for every domain-category cell;
- all 20 candidates pass schema and source-resolution checks;
- the review workflow distinguishes acceptance, revision, and rejection;
- accepted records can be frozen without inspecting path results;
- frozen questions can be executed through all six paths and exported for
  blinded evidence review.

The success criterion is workflow reliability and category constructibility,
not router improvement.

## 12. Implementation Boundary

The implementation includes:

- `docs/annotation/question-construction-v1.md`;
- `docs/annotation/evidence-labeling-v1.md`;
- read-only candidate selectors;
- an ignored local authoring area for 20 question/specification pairs;
- pre-freeze validation and review import/export;
- normalized prior-question duplicate checking;
- immutable question freezing;
- six-path execution for accepted frozen questions;
- method-blinded evidence-review export.

It excludes:

- a browser or desktop annotation platform;
- automatic LLM evidence judgments;
- multimodal table recognition;
- router training, calibration, or abstention evaluation;
- production of the remaining 100 Pilot questions;
- changes to the six frozen paths.
