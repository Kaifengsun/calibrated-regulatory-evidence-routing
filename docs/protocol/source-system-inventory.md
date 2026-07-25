# Source-System Inventory

Date: 2026-07-23

Status: Phase 1 read-only inventory

Rule: source roots are supplied through local environment variables and are never committed.

## 1. Chemical-safety source system

Configuration alias: `CER_CHEMICAL_PROJECT_ROOT`

### Reusable entry point

Primary reference implementation:

- `experiments/evaluate_independent_query_benchmark.py`
- SHA-256: `8845FF1BBFBDC08392B23B67A4BB0ECAD144430D401FFA6E174187C143AD4781`
- The source directory is not a Git repository, so the file hash and later live corpus manifest must identify the reused state.

### Retrieval contract

- Backend: read-only Neo4j session.
- Required configuration names: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, and optional `NEO4J_DATABASE`.
- BM25 index: `section_fulltext_cjk`.
- Existing query behavior: Lucene-special characters are replaced with spaces; results are ordered by score descending.
- Existing experimental depth: configurable, with the new Pilot fixed at BM25 top 50 and presentation cutoff 10.
- Existing result identity: Neo4j `elementId`.
- Live verification correction: expose globally unique `Section.uid` as the
  stable public source identifier and retain `elementId` only as a runtime
  locator. `Section.doc_id` is a legacy, non-unique structural identifier.

### Available provenance and context

- Nodes: `Standard`, `Section`, `Table`, and `QAPair`.
- Hierarchy: `Standard-[:HAS_SECTION]->Section` and `Section-[:HAS_SUBSECTION]->Section`.
- Table context: `Section-[:HAS_TABLE]->Table`.
- Logical relations: outgoing `Section-[:CITES|DEPENDS_ON]->Section`.
- Relation confidence: stored on the relationship and already used with threshold `0.85`.
- Relevant Section fields observed in the existing experiment and manuscript artifacts include `doc_id`, standard linkage, section title/number, original/source text, expanded content, and source location.

### Pilot adapter recommendation

Implement a thin Neo4j adapter that:

1. runs one `section_fulltext_cjk` query and returns score-bearing top-50 Sections;
2. resolves stable `uid` plus attributable Section fields in the same read transaction;
3. loads heading path, immediate parent, and directly attached table metadata on demand;
4. returns metadata-only counts and maximum confidence for outgoing `CITES` and `DEPENDS_ON`;
5. expands only outgoing Section-to-Section relations with confidence at least `0.85`.

Do not import the production web-service orchestration layer, QAPair retrieval, vector retrieval, answer generation, or legacy `HAS_QAPAIR` relationships.

### Required service

A compatible Neo4j database containing the frozen manuscript snapshot must be reachable during integration testing and Pilot execution. Phase 1 does not start or modify that database.

## 2. Pharmaceutical-regulatory source system

Configuration alias: `CER_PHARMA_PROJECT_ROOT`

### Reusable state

- Git commit inspected: `34efc79aeb3c190aa6253fece8d884dc38c405a4`
- The source worktree contains unrelated untracked files; this project will read tracked or explicitly inventoried artifacts only and will not modify the source worktree.
- Frozen enriched corpus: 99 files, 15,524,824 bytes in the existing enrichment snapshot.
- Aggregate corpus SHA-256: `7dbc24dc74628d5e2bb45427d38d5da10d5ca75515c60cee1c58aa3d72cbe031`.
  This digest is the SHA-256 of the UTF-8, newline-joined list of
  `filename<TAB>lowercase-file-sha256` entries sorted by filename.
- Stable source identifier: `chunk_id`.
- Document identifier: `doc_id`.

Reference implementation hashes:

- `source_chunk_reranker.py`: `B1FF14705D59388B4E3996218C437DE952C1FBE7408CC39FA9BA2326AA175203`
- `tools/modern_reranker_58/common.py`: `A812433C6E4088BD0B3542C28871A167BDFAA91D3024A527BC79CE0C43C0A4F0`
- `tools/modern_reranker_58/run_locked_reranker.py`: `A3C494639B66EDF3963AC448A2BEFAF19D8E9BFBFE2513A4876AC9232F85A5DC`

Frozen graph snapshot hashes:

- `nodes.jsonl`: `4eba23690803e4dd749db52d1740c10b51515eef3053f099dc32b9d3435a63c7`
- `edges.jsonl`: `522b67d03821d104489529aae1fcdca3d5714e0895d62aefd3d9c4f2df056502`
- `graph_extension_manifest.json`: `b98be3237f59eb930a5e3cfeb92ec82ef97f4d18867924932bbdc46d6bfb58b2`

### Retrieval contract

- BM25 implementation: deterministic in-memory `BM25Index`.
- Indexed source text: `parents_context`, `heading`, and the first 2,000 content characters.
- Parameters: `k1=1.2`, `b=0.75`.
- Stable ordering: score descending, then original corpus order.
- Neural reranker: locked Qwen3 yes/no relevance scoring over BM25 top 50.
- Existing model ID: `Qwen/Qwen3-Reranker-0.6B`.
- Existing input maximum: 1,024 tokens.
- Existing stable reranker ordering: score descending, BM25 rank ascending, then `chunk_id`.

### Available provenance and context

- Source records include `chunk_id`, `doc_id`, `heading`, `content`, and `parents_context`.
- The frozen graph snapshot contains `DocChunk`, `RegulatoryDocument`, `Table`, and structured supply-chain nodes.
- Hierarchy and context relations include `PARENT_OF`, `CONTAINS`, `NEXT`, and `HAS_TABLE`.
- Tables are linked through `DocChunk-[:HAS_TABLE]->Table`.

### Relation mismatch requiring protocol resolution

The frozen pharmaceutical graph has no native `CITES` or `DEPENDS_ON` relationship labels. It contains:

- 602 `REFERENCES` edges;
- 1 `REQUIRES_COMPLIANCE_WITH` edge;
- 1 `APPLIES_DEFINITION_FROM` edge;
- 7 `USES_PRINCIPLES_FROM` edges;
- 2 `INTERPRETS` edges.

Most `REFERENCES` edges connect a `DocChunk` to a `RegulatoryDocument` or `RegulatoryReference`, rather than directly to another `DocChunk`. Therefore the chemical P3 query cannot be copied unchanged.

Recommended minimal resolution for Phase 2:

- preserve every original pharmaceutical edge label and path;
- expose a normalized logical `CITES` candidate only for an explicit `REFERENCES` edge that resolves deterministically to one target document and one attributable target chunk;
- expose a normalized logical `DEPENDS_ON` candidate only for explicit `REQUIRES_COMPLIANCE_WITH`, `APPLIES_DEFINITION_FROM`, `USES_PRINCIPLES_FROM`, or `INTERPRETS` provenance that resolves deterministically to attributable source text;
- exclude ambiguous or non-textual targets rather than adding heuristic multi-hop inference.

This normalization is not yet frozen. It requires a narrow amendment to the Pilot protocol before path execution. It does not require a new graph, Agent, or general multi-hop system.

### Pilot adapter recommendation

Implement a thin snapshot adapter that:

1. loads the frozen enriched JSON corpus without copying it;
2. reuses the deterministic BM25 source-text contract;
3. attaches `parents_context` and directly linked table metadata as sidecars;
4. calls the frozen Qwen3 reranker through a small local wrapper;
5. exposes only protocol-approved normalized logical relations with full original provenance.

Do not import the legacy Neo4j retriever, FAISS first-stage retrieval, HyDE, LLM graph walking, supply-chain simulation, or generated-answer components.

## 3. Unified field mapping

| Unified field | Chemical source | Pharmaceutical source |
|---|---|---|
| `domain` | constant `chemical` | constant `pharmaceutical` |
| `source_id` | unique `Section.uid` | `chunk_id` |
| `runtime_locator` | Neo4j `elementId` | `chunk_id` |
| `document_id` | Standard/Section document identifier | `doc_id` |
| `heading` | Section title/number | `heading` |
| `content` | attributable Section source text | `content` |
| `parent_context` | immediate parent Section | `parents_context` |
| `table_context` | linked Table title/description | linked Table metadata or frozen table record |
| `relation_type_original` | `CITES` or `DEPENDS_ON` | approved explicit source relation |
| `relation_type_normalized` | unchanged | protocol-approved `CITES` or `DEPENDS_ON` |
| `relation_confidence` | stored confidence | deterministic resolution status; numeric policy not yet frozen |
| `provenance` | graph and source location fields | snapshot provenance plus graph edge path |

## 4. Phase 1 conclusion

BM25, context, stable identifiers, and the locked reranker can be reused with thin adapters. No service rewrite is justified.

The only material incompatibility is the pharmaceutical relation schema. Phase 2 must freeze a conservative normalization and confidence rule before P3/P5 implementation. Until that amendment is approved, the relation path is a documented protocol dependency rather than an implementation target.

## 5. Phase 3 verification update

On 2026-07-24, the pharmaceutical adapter loaded the frozen snapshot read-only,
validated 2,478 unique chunks, reproduced the aggregate corpus hash recorded
above, and returned deterministic BM25 candidates. The conservative relation
normalizer returned no eligible graph target for the five seeds in the smoke
query; it did not guess a target section inside a referenced document.

On 2026-07-25, path-blind candidate discovery inspected the complete
pharmaceutical normalized-edge index rather than only five smoke-test seeds.
The graph contains the documented explicit document-level relations, but none
resolves uniquely to one attributable target chunk under the frozen
normalization rule. The adapter therefore exposes zero eligible pharmaceutical
`CITES` or `DEPENDS_ON` targets. Direct, parent/heading, and table candidate
structures are available; pharmaceutical `citation_dependency` question
construction remains blocked pending an explicit protocol decision. No
heuristic target-chunk selection was introduced.

The chemical Neo4j adapter is implemented and passes a query-contract fixture
that rejects write clauses. The live instance is available through its
non-default local Browser and Bolt ports. Read-only verification found 9,206
`Standard` nodes and 991,453 `Section` nodes. All Sections have globally unique
`uid` values, while only 888,943 distinct legacy `doc_id` values exist. The
adapter therefore verifies and queries `uid`; `standard_uid` supplies document
grouping, and `doc_id` is not used as evidence identity.

Live smoke tests then verified all of the following without returning or
modifying source text:

- BM25 results expose `uid` and resolve back to the same Section;
- heading and immediate-parent context are available;
- a Section with `HAS_TABLE` returns a table sidecar;
- metadata lookup and one-hop expansion agree on an eligible `CITES` target
  with stored confidence at least `0.85`.

The live check used a placeholder corpus hash solely to exercise the adapter.
A deterministic fingerprint of the complete chemical snapshot must be
generated and frozen before Pilot questions or path outputs are created.
