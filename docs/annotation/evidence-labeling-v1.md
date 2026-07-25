# Evidence Labeling Guide v1

## 1. Purpose and Unit of Review

Evidence is labeled only after a question and its evidence specification have
been frozen and all six paths have run. The reviewer labels each ranked unit
within the top 10 and each eligible context sidecar attached to a top-five
seed. A seed and its sidecar are separate evidence units.

Paths are method-blinded during review. Labels describe the relationship
between one evidence unit and the frozen question, not whether the reviewer
likes the retrieval method.

## 2. Five Labels

### REQUIRED

Use `REQUIRED` when the unit supplies an indispensable part of a multi-unit
evidence specification. Removing it would make the evidence package
incomplete.

Example, chemical:

- One clause defines which storage class applies.
- A second required table supplies the permitted quantity.
- Neither unit alone is complete; both are `REQUIRED`.

Example, pharmaceutical:

- A direct provision establishes who must report.
- A cited provision establishes the reporting deadline.
- Both units are `REQUIRED`.

### SUFFICIENT

Use `SUFFICIENT` when the unit alone fully answers a single-item evidence
specification at the required scope and specificity.

Example, chemical:

- The clause states the applicable condition and the complete required
  protective measure.

Example, pharmaceutical:

- The provision states the complete record-retention period and regulated
  party.

Do not label a merely relevant fragment as `SUFFICIENT`.

### CONTEXT

Use `CONTEXT` when the unit improves interpretation or attribution but is not
required under the frozen evidence specification.

Examples:

- a heading that confirms the topic already stated completely in the child
  clause;
- a parent paragraph that provides useful background without changing the
  answer;
- a table title that helps identify a table whose required value is separately
  represented.

A sidecar is not automatically `CONTEXT`; it can be `REQUIRED`, `SUFFICIENT`,
`IRRELEVANT`, or `HARMFUL`.

### IRRELEVANT

Use `IRRELEVANT` when the unit does not contribute to the complete answer but
does not materially mislead the regulatory interpretation.

Examples:

- a neighboring clause about a different operational detail;
- duplicated correct evidence;
- broadly related background;
- a weak topical match with no contradictory scope.

Irrelevant evidence does not by itself make a path fail.

### HARMFUL

Use `HARMFUL` only when including the unit could materially change or corrupt
the regulatory interpretation. Apply the decision order in Section 4.

Any harmful ranked unit or eligible sidecar in the evaluated package makes
combined path success zero, even if complete evidence is also present.

## 3. Labeling Procedure

For each question:

1. Read the frozen question and evidence-scope note.
2. Review the required and sufficient source identifiers.
3. Review each blinded evidence unit independently.
4. Assign exactly one of the five labels.
5. For `HARMFUL`, select exactly one primary harmful-reason code.
6. After all units are labeled, calculate evidence completeness.
7. Separately record whether any harmful expansion occurred.
8. Derive combined path success from completeness and harm.

Do not change the evidence specification during annotation. If it is defective,
flag the question for adjudication and suspend its final label freeze.

## 4. HARMFUL Decision Order

Test the following conditions in order and use the first applicable primary
reason:

1. `wrong_version`: the unit comes from an obsolete, superseded, or otherwise
   wrong regulatory document version whose rule differs materially.
2. `wrong_regulated_object`: the unit concerns the wrong product, substance,
   organization, jurisdiction, or regulated object.
3. `wrong_scope_condition_or_exception`: the unit changes the applicable
   scope, responsible party, condition, threshold, or exception.
4. `direct_conflict`: the unit directly contradicts the correct evidence.
5. `materially_misleading`: another material defect is likely to alter the
   regulatory interpretation.

If none applies, use `IRRELEVANT` rather than stretching `HARMFUL`.

## 5. HARMFUL Examples

### 5.1 Chemical-Safety Positive Examples

- The question concerns current storage requirements, but the retrieved unit
  states a materially different threshold from a superseded version:
  `HARMFUL / wrong_version`.
- The question concerns flammable-liquid storage, but the unit gives an
  incompatible rule for explosives and could be mistaken as applicable:
  `HARMFUL / wrong_regulated_object`.
- The correct clause applies indoors, while the unit supplies a conflicting
  outdoor exception without identifying the changed scope:
  `HARMFUL / wrong_scope_condition_or_exception`.

### 5.2 Chemical-Safety Negative Examples

- A general definition of hazardous chemicals that does not answer the storage
  question: `IRRELEVANT`.
- The same correct clause retrieved twice: one may be evidentially sufficient
  and the duplicate is `IRRELEVANT`; duplication alone is not harmful.
- A nearby inspection requirement with no conflicting instruction:
  `IRRELEVANT`.

### 5.3 Pharmaceutical Positive Examples

- The question concerns an active FDA obligation, but the unit presents a
  withdrawn rule with a different deadline: `HARMFUL / wrong_version`.
- The question concerns manufacturers, while the unit imposes a materially
  different obligation on sponsors and could change the responsible party:
  `HARMFUL / wrong_scope_condition_or_exception`.
- The correct evidence requires retention for one period, while the unit
  explicitly states an incompatible period for the same situation:
  `HARMFUL / direct_conflict`.

### 5.4 Pharmaceutical Negative Examples

- A general policy statement that lacks the requested deadline: `IRRELEVANT`.
- A provision governing another reporting form but not contradicting the
  requested obligation: `IRRELEVANT`.
- A heading that confirms the section topic but adds no required fact:
  `CONTEXT`, not `HARMFUL`.

## 6. Evidence Completeness

A path is complete when either:

- every `required_source_id` in the frozen specification appears among its
  evaluated ranked units or eligible sidecars; or
- at least one `sufficient_source_id` appears for a single-item specification.

Evidence completeness ignores harmful status. This separation allows reporting
whether a path failed because it missed evidence or because it added dangerous
material.

For an insufficiency candidate, no path can be declared complete merely because
it retrieved related material.

## 7. Harmful Expansion and Combined Success

Report three results separately:

- evidence completeness;
- harmful expansion rate;
- combined path success.

Combined path success equals one only when evidence is complete and no evaluated
unit is harmful. Ordinary irrelevant evidence does not force failure.

The strict harmful rule is intentional for regulatory retrieval. The paper
must describe it as a risk-averse operational definition rather than a
universal relevance metric.

## 8. Corpus Insufficiency

Six failed paths do not establish corpus insufficiency. A reviewer must inspect
the frozen corpus and complete a `ManualSearchRecord`.

The manual procedure includes:

1. identifier or known-source lookup when applicable;
2. title or metadata lookup;
3. full-text searches using documented synonyms and scope terms;
4. graph-relation inspection when a cited dependency is plausible;
5. manual document browsing when automated search remains ambiguous.

The reviewer records the corpus scope, methods, query terms, result, and
rationale. Mark the corpus `insufficient` only when the completed search finds
no complete attributable evidence. If evidence exists but no path retrieved it,
the outcome is retrieval failure.

## 9. Difficult Cases

- If a unit contains both useful and harmful statements, label it `HARMFUL`
  because the evaluated unit is delivered as a whole.
- If the evidence identifier is correct but the displayed content is truncated
  before the required fact, do not label it `SUFFICIENT`; flag the packaging
  defect.
- If two units restate the same complete rule, each can be `SUFFICIENT` only
  when either independently satisfies the specification.
- If a parent changes material scope, it can be `REQUIRED`; parent status does
  not imply `CONTEXT`.
- If a graph target is correctly cited but unrelated to the question, label it
  `IRRELEVANT` unless it materially misleads.

## 10. Review Integrity

Do not edit immutable question, path, rank, evidence, source, or sidecar
identities in the workbook. Use comments or the designated issue field to flag
problems. Import rejects identity changes.

Primary, duplicate, and adjudicated annotations remain separate in the formal
120-question Pilot. This 20-question workflow batch requires primary review
only; it does not waive the later requirement for 30 independently duplicated
questions.
