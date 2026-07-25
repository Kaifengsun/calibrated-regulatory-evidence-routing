# Domain-Available Category Quotas Amendment

**Status:** Approved before question and path-label freeze
**Date:** 2026-07-25

## 1. Reason for Amendment

Complete path-blind inspection of the frozen pharmaceutical graph found no
explicit relation that resolves uniquely to one attributable target text chunk
under the conservative normalization rule. The graph contains document-level
references, but selecting a substantive target clause would require heuristic
or manually authored target mapping.

The Pilot will not introduce such mapping. Category quotas are therefore
aligned with evidence structures available in each frozen domain. This
amendment occurs before any Pilot question or path label is frozen.

## 2. Unchanged Scope

The Pilot retains:

- exactly 120 questions;
- exactly 60 chemical-safety and 60 pharmaceutical-regulatory questions;
- the same five construction-category definitions;
- all six paths `P0` through `P5` in both domains;
- the same success, cost, calibration, abstention, and Go/No-Go definitions.

`P3` and `P5` continue to run on pharmaceutical questions. Under the frozen
snapshot, their graph stage inserts zero targets; their other stages remain
operational.

## 3. Full Pilot Quotas

| Domain | Direct | Parent/heading | Table | Citation dependency | Evidence insufficient | Total |
|---|---:|---:|---:|---:|---:|---:|
| Chemical safety | 12 | 12 | 12 | 12 | 12 | 60 |
| Pharmaceutical regulation | 15 | 15 | 15 | 0 | 15 | 60 |
| Total | 27 | 27 | 27 | 12 | 27 | 120 |

The chemical domain retains the original five-category balance. The
pharmaceutical domain is balanced across its four constructible categories.

## 4. Twenty-Question Pre-Freeze Batch

| Domain | Direct | Parent/heading | Table | Citation dependency | Evidence insufficient | Total |
|---|---:|---:|---:|---:|---:|---:|
| Chemical safety | 2 | 2 | 2 | 2 | 2 | 10 |
| Pharmaceutical regulation | 3 | 3 | 2 | 0 | 2 | 10 |
| Total | 5 | 5 | 4 | 2 | 4 | 20 |

This batch remains a workflow validation set, not an estimate of category
prevalence.

## 5. Duplicate-Annotation Allocation

Exactly 30 complete questions still receive independent duplicate annotation:

| Domain | Direct | Parent/heading | Table | Citation dependency | Evidence insufficient | Total |
|---|---:|---:|---:|---:|---:|---:|
| Chemical safety | 3 | 3 | 3 | 3 | 3 | 15 |
| Pharmaceutical regulation | 4 | 4 | 4 | 0 | 3 | 15 |
| Total | 7 | 7 | 7 | 3 | 6 | 30 |

The pharmaceutical evidence-insufficient cell receives three rather than four
duplicate questions because its manual negative-search review has the highest
human cost.

## 6. Analysis Consequences

- Category-stratified summaries report the actual domain-category counts.
- No pharmaceutical citation-dependency estimate is reported.
- Graph-stage benefit in Go/No-Go Signal 2 can arise only from chemical
  questions.
- Cross-domain transfer remains descriptive. A pharmaceutical-trained router
  has no positive graph-stage examples, and this limitation must be stated when
  interpreting transfer to chemical safety.
- Domain and graph-availability features may represent the observable
  difference, but path results and manually authored graph targets remain
  prohibited route-time inputs.
- Overall results use the fixed 120-question population and must not be
  presented as category-balanced macro estimates.

## 7. Validation Changes

Configuration and freeze validation must:

- store explicit integer quotas for every domain-category cell;
- require every domain total to equal 60 and the grand total to equal 120;
- require the 20-question pre-freeze quotas shown above;
- require the 30-question duplicate-allocation quotas shown above;
- reject any pharmaceutical `citation_dependency` question;
- preserve chemical graph confidence and relation rules unchanged.

## 8. Rejected Alternatives

- Heuristically choose one chunk from a referenced pharmaceutical document:
  rejected because the target is not uniquely attributable.
- Add manual source-to-target graph mappings during question authoring:
  rejected because it leaks authored evidence into the retrieval graph.
- Replace the pharmaceutical corpus or rebuild its graph:
  rejected as disproportionate for the target publication level.
- Remove graph routing entirely:
  rejected because the chemical corpus contains sufficient eligible relations
  to test the stage.
