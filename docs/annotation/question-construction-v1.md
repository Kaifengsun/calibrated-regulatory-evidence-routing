# Pilot Question Construction Guide v1

## 1. Purpose

This guide governs the 20-question workflow-validation batch and the later
120-question Pilot. Its purpose is to create realistic regulatory information
needs without using retrieval results to manufacture favorable path
differences.

The observation unit used later is a question-path pair, but question authors
work only from frozen source evidence. They must not inspect `P0` through `P5`
outputs until the question and evidence specification have been accepted and
frozen.

## 2. Pre-Freeze Batch Quota

The first batch contains exactly 20 questions:

| Domain | Language | Questions per category | Total |
|---|---|---:|---:|
| Chemical safety | Chinese | 2 | 10 |
| Pharmaceutical regulation | English | 2 | 10 |

The five categories are:

1. `direct_clause`;
2. `parent_heading_context`;
3. `table_related`;
4. `citation_dependency`;
5. `evidence_insufficient`.

The balanced batch verifies that the workflow can construct every category. It
does not estimate the natural frequency of those categories.

## 3. Authoring Sequence

Use this order for every candidate:

1. Confirm that the source belongs to the frozen domain corpus.
2. Identify a realistic regulatory information need.
3. Identify all evidence required for a complete answer.
4. Create an `EvidenceSpecification`.
5. Write the question in natural language.
6. Assign the proposed construction category and any counter-cue tags.
7. Check for overlap with prior-manuscript questions.
8. Resolve every evidence identifier against the frozen corpus.
9. Export the candidate for pre-freeze human review.
10. Freeze accepted records before running any evidence path.

Do not revise a question because one path performed unexpectedly. A legitimate
post-freeze correction creates a new version and invalidates the earlier path
outputs.

## 4. General Question Rules

A valid question must:

- resemble something a compliance, safety, quality, or regulatory user might
  genuinely ask;
- be answerable at the level of specificity represented by its evidence
  specification;
- avoid unnecessary standard numbers, clause numbers, document titles, and
  verbatim answer phrases;
- identify the regulated object or situation clearly enough to avoid accidental
  ambiguity;
- remain understandable without access to the authoring notes;
- use Chinese for chemical-safety questions and English for pharmaceutical
  questions;
- be newly written rather than lightly paraphrased from an earlier evaluation
  question.

Avoid compound questions that test several unrelated obligations. Multiple
evidence units are acceptable only when they jointly answer one coherent
information need.

## 5. Category Rules

### 5.1 Direct Clause

Use `direct_clause` when one attributable direct text unit fully answers the
question without a parent, table, or cited target.

Acceptable pattern:

> 在某一明确作业条件下，操作人员必须采取什么措施？

The source clause itself must state both the condition and required measure.

Reject or recategorize when:

- the direct text omits the applicable subject or scope;
- a table value is needed;
- the clause says only “in accordance with” another provision;
- several clauses are required to reconstruct the answer.

### 5.2 Parent or Heading Context

Use `parent_heading_context` when a direct unit is semantically incomplete
without an eligible heading or immediate parent. The context must determine
material scope, subject, condition, or interpretation.

Acceptable pattern:

> Which organization is responsible for the listed reporting action?

The child text may list the action while its parent establishes the responsible
organization.

Do not use this category merely because a heading is informative. If the direct
clause already gives a complete answer, it remains `direct_clause`.

### 5.3 Table Related

Use `table_related` only when an existing attributable table-text sidecar is
required for complete evidence. Current scope includes extracted table text,
titles, descriptions, and stable table identities; it excludes image
recognition and cell detection from unprocessed images.

Acceptable pattern:

> 某类装置在给定规格下允许的最大间距是多少？

The requested value must be found in an eligible table.

A question that mentions “table” but is fully answered in prose is not
`table_related`; it may be retained as a counter-cue case in another category.

### 5.4 Citation Dependency

Use `citation_dependency` when the direct source requires one deterministic
outgoing `CITES` or `DEPENDS_ON` target for a complete answer. The normalized
relation must be eligible under the frozen graph rule and have confidence at
least 0.85.

Acceptable pattern:

> What underlying requirement must be followed when carrying out this
> inspection?

The direct clause identifies the dependency, and the graph target states the
substantive requirement.

Do not use this category when the direct clause restates the cited requirement
completely. Mentioning another regulation does not by itself make a question
dependent.

### 5.5 Evidence Insufficient

Use `evidence_insufficient` when the frozen corpus does not contain all evidence
needed for a complete answer. This status cannot be inferred from retrieval
failure.

Before acceptance, a reviewer must complete a `ManualSearchRecord` documenting:

- the frozen corpus scope searched;
- search methods;
- query terms;
- whether attributable evidence was found;
- why the remaining evidence is insufficient.

Do not manufacture unanswerable questions through vague wording, nonexistent
objects, future events, or trivia unrelated to the corpus.

## 6. Evidence Specification Rules

Use `sufficient_source_ids` when any one listed item independently supplies a
complete answer. Use `required_source_ids` when every listed item is necessary.
The same identifier cannot appear in both lists.

For `evidence_insufficient`, set `insufficiency_candidate` to `true` and leave
both evidence lists empty. Do not invent a missing source identifier.

The `evidence_scope_note` briefly states why the listed evidence is complete.
It must not describe expected path behavior.

## 7. Counter-Cue Construction

Across the batch, include applicable examples of:

- relation language where direct evidence is sufficient;
- no relation language where a cited target is required;
- table wording where prose supplies the answer;
- a plausible retrieval distractor with the wrong object, scope,
  jurisdiction, or version.

Counter cues prevent category prediction from collapsing into keyword rules.
They must arise naturally from the information need. Record each one in
`counter_cue_tags` and explain it in the private authoring record.

## 8. Prior-Question Non-Overlap

Before acceptance:

1. normalize whitespace, punctuation, and case;
2. compare against both earlier manuscripts' evaluation questions;
3. reject exact normalized matches;
4. flag high lexical overlap for human review;
5. compare the requested fact, source family, and evidence structure;
6. rewrite or replace any candidate that materially reproduces an earlier
   evaluation item.

Shared regulatory terminology alone is not duplication. The check concerns the
information need and evidence target, not isolated words.

## 9. Source-to-Question Audit Checklist

The reviewer answers every item:

- Is the source in the frozen corpus and permitted domain scope?
- Does every evidence identifier resolve uniquely?
- Does the evidence completely support the intended answer?
- Is the question natural and sufficiently specific?
- Does the wording avoid unnecessary answer leakage?
- Is the proposed category determined by evidence structure?
- Are counter-cue tags justified?
- Is the source group correct?
- Has prior-question overlap been checked?
- For insufficiency, is the manual search complete?

## 10. Review Decisions

- `accept`: all checks pass; the record may be frozen.
- `revise_and_review`: wording, specification, category, or metadata needs a
  correctable change; the revised record must be reviewed again.
- `reject_and_replace`: the information need is unsuitable, duplicative, or
  unsupported; create a new candidate.

An accepted record requires resolved sources, a clear prior-question check,
reviewer identity, and a timezone-aware review timestamp.

## 11. Data Handling

Tracked files may contain schemas, fictional templates, instructions, and
redistribution-safe identifiers. Real source excerpts, reviewer workbooks,
manual-search notes, and local source locations remain under the ignored
private authoring directory.
