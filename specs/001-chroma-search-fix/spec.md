# Feature Specification: ChromaDB Search Quality Investigation & Fix

**Feature Branch**: `001-chroma-search-fix`
**Created**: 2026-01-24
**Status**: Draft
**Input**: User description: "we need to investigate why memoria is now with current data on chroma always only returning a single element for any query with from 0.4 to 0.6 assurance, this is extremely weird and seems wrong. Besides investigation we need fix it likely with using more vector algorythms possible to spread vector space between elements and find bette matches of terms?"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - RAG Query Returns Multiple Relevant Results (Priority: P1)

When users query the memoria RAG system with technical questions, they should receive multiple relevant documents ranked by relevance, not just a single result. Currently, all queries return only one result with low confidence scores (0.4-0.6), severely limiting the system's usefulness.

**Why this priority**: This is the core functionality of the RAG system. A RAG that returns only one result is essentially broken and prevents users from discovering related information, comparing approaches, or understanding the full context of their queries.

**Independent Test**: Can be fully tested by executing 10 diverse queries against the existing ChromaDB collection (2837 docs, 1793+ chunks) and verifying that each query returns 3-10 results with varying relevance scores (0.3-0.9 range) instead of a single result with 0.4-0.6 score.

**Acceptance Scenarios**:

1. **Given** memoria RAG has 2837 documents indexed, **When** user queries "claude loop protocol", **Then** system returns 5-10 results with relevance scores ranging from 0.3 to 0.8, ordered by relevance
2. **Given** memoria RAG has 1793+ chunks indexed, **When** user queries "agent catalog", **Then** system returns multiple agent-related documents with different confidence scores, not just one result
3. **Given** current broken state returns single result, **When** search fix is applied, **Then** same query now returns 5+ results with diverse relevance scores

---

### User Story 2 - Confidence Scores Reflect True Relevance (Priority: P1)

Users need confidence scores that accurately reflect how well results match their query, with high-relevance matches scoring 0.7-0.9 and lower-relevance matches scoring 0.3-0.5. Currently, all results cluster in the 0.4-0.6 range regardless of actual relevance.

**Why this priority**: Without accurate confidence scores, users cannot distinguish highly relevant results from marginally relevant ones. This makes the RAG system unusable for automated decision-making (e.g., determining whether RAG has relevant info before responding).

**Independent Test**: Can be tested by comparing confidence scores for known high-relevance queries (e.g., querying for exact document titles) versus low-relevance queries (e.g., unrelated terms). High-relevance queries should score 0.7+, low-relevance should score <0.5.

**Acceptance Scenarios**:

1. **Given** a query matches document content exactly, **When** search is executed, **Then** top result has confidence score ≥0.7
2. **Given** a query uses synonyms or related terms, **When** search is executed, **Then** results have graduated confidence scores (0.5-0.7 range)
3. **Given** a query is tangentially related to content, **When** search is executed, **Then** results have lower confidence scores (0.3-0.5 range)

---

### User Story 3 - Semantic Search Finds Conceptually Related Results (Priority: P2)

Users should be able to find documents using conceptual queries, not just exact keyword matches. The vector search should leverage embedding similarity to find documents that discuss the same concept using different terminology.

**Why this priority**: Semantic search is the key advantage of vector databases over traditional keyword search. Without it, users must guess exact terminology used in documents, severely limiting discoverability.

**Independent Test**: Can be tested by querying with synonyms, paraphrases, or conceptual descriptions (e.g., "how to commit code" vs "git commit protocol") and verifying that both queries return overlapping relevant results.

**Acceptance Scenarios**:

1. **Given** documents use term "RAG compliance monitoring", **When** user queries "query tracking system", **Then** system returns those documents via semantic similarity
2. **Given** documents describe "specialized agents", **When** user queries "task-specific AI workers", **Then** system finds relevant agent documentation
3. **Given** technical documentation uses formal language, **When** user queries in casual language, **Then** system bridges terminology gap via embeddings

---

### User Story 4 - Investigation Reveals Root Cause (Priority: P1)

The development team needs to understand why the vector search degraded to returning single results with clustered confidence scores. Investigation should identify specific misconfigurations, algorithm issues, or data problems.

**Why this priority**: Without understanding root cause, any fix is just guesswork. Investigation must precede implementation to ensure the fix addresses actual problems, not symptoms.

**Independent Test**: Investigation is complete when it produces a diagnostic report identifying: (1) vector space characteristics (dimensionality, density, distribution), (2) embedding quality metrics, (3) similarity algorithm behavior, (4) any configuration drift from known-good state.

**Acceptance Scenarios**:

1. **Given** ChromaDB collection with 1793+ chunks, **When** vector space is analyzed, **Then** report shows whether vectors are clustered or well-distributed
2. **Given** current queries return 0.4-0.6 scores, **When** similarity calculation is traced, **Then** investigation reveals why scores don't differentiate between results
3. **Given** system previously worked better, **When** configuration is compared to baseline, **Then** investigation identifies what changed

---

### Edge Cases

- What happens when query embeddings are very similar to multiple documents (ambiguous queries)?
- How does system handle queries with no relevant results (should return empty set or low-confidence results)?
- What happens when ChromaDB collection grows to 10,000+ documents (does vector space become more or less discriminative)?
- How does system behave with very short queries (1-2 words) versus detailed queries (full sentences)?
- What happens if embedding model changes (do existing vectors become incompatible)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST return multiple results (3-10) for queries when relevant documents exist in the collection
- **FR-002**: System MUST produce confidence scores that span a meaningful range (0.2-0.9) based on actual relevance, not cluster in narrow band
- **FR-003**: Investigation MUST analyze current vector space characteristics including dimensionality, distribution, and density
- **FR-004**: Investigation MUST compare current ChromaDB configuration against known-good baseline configuration
- **FR-005**: Investigation MUST test multiple distance/similarity metrics (cosine, euclidean, dot product) to identify if current metric is suboptimal
- **FR-006**: System MUST support configurable similarity thresholds to filter very low-relevance results (e.g., <0.3)
- **FR-007**: Investigation MUST examine embedding quality by testing known-good query-document pairs
- **FR-008**: Fix MUST preserve existing indexed documents and embeddings unless investigation proves they are corrupt
- **FR-009**: System MUST provide diagnostic output showing why each result was scored at its confidence level
- **FR-010**: Fix MUST be validated against diverse query types (exact matches, synonyms, conceptual queries, edge cases)

### Non-Functional Requirements

- **NFR-001**: Search queries MUST complete within 2 seconds for collections up to 5000 documents
- **NFR-002**: Investigation MUST produce human-readable diagnostic report documenting findings
- **NFR-003**: Fix MUST be backward compatible with existing RAG query interface (search_knowledge function)
- **NFR-004**: System MUST maintain query performance (throughput) while improving result quality

### Key Entities

- **ChromaDB Collection**: The vector database storing 2837 documents and 1793+ embeddings. Key attributes: collection name, embedding model, distance metric, dimensionality.
- **Query Embedding**: Vector representation of user's search query. Must be computed with same model as document embeddings.
- **Search Results**: Set of documents with confidence scores. Attributes: document content, metadata, relevance score, rank.
- **Distance Metric**: Algorithm used to compute similarity between query and document embeddings (cosine, euclidean, dot product). Critical configuration affecting result quality.
- **Vector Space**: N-dimensional space where embeddings exist. Characteristics: distribution spread, clustering patterns, separation between distinct concepts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 90% of test queries return 5+ results (up from current 100% returning exactly 1 result)
- **SC-002**: Confidence scores span at least 0.4 range (e.g., top result 0.8, 5th result 0.4) instead of clustering in 0.2 range
- **SC-003**: Known high-relevance queries (exact terminology matches) score ≥0.7 confidence
- **SC-004**: Semantic queries (synonym/paraphrase variations) successfully retrieve target documents in top 5 results
- **SC-005**: Investigation produces diagnostic report documenting root cause within 2 working days
- **SC-006**: Fix maintains or improves query performance (search completes in <2 seconds)
- **SC-007**: User satisfaction with RAG results improves (measured by explicit "results were useful" feedback or follow-up query rate reduction)

## Assumptions

- Current ChromaDB installation is functioning correctly at the infrastructure level (database not corrupted)
- Existing embeddings were generated with a consistent model (no model drift during indexing)
- Issue is recent and likely due to configuration change, not gradual degradation
- Standard embedding models (sentence-transformers or similar) are being used
- Investigation has access to ChromaDB admin interface and configuration files
- Test queries representing real user needs are available or can be synthesized from RAG usage logs

## Dependencies

- Access to ChromaDB database and configuration files
- Access to memoria RAG codebase (skill_helpers.py, raggy.py)
- Sample queries or usage logs to validate fix against real user patterns
- Baseline configuration or documentation of known-good system state (if available)
- ChromaDB documentation for advanced configuration options

## Out of Scope

- Migrating to different vector database (e.g., Pinecone, Weaviate) - focus is fixing ChromaDB
- Retraining or replacing embedding model - assume current model is adequate
- Re-indexing entire document collection - preserve existing embeddings unless proven corrupt
- Building new RAG features (e.g., hybrid search, re-ranking) - focus on fixing core search quality
- Performance optimization beyond maintaining current <2 second query time

## Investigation Plan

### Phase 1: Data Collection (Day 1, Morning)

1. **Capture Current Behavior**:
   - Execute 20 diverse test queries documenting exact results and scores
   - Log ChromaDB collection statistics (document count, embedding dimensions, index type)
   - Review current configuration files and compare to ChromaDB defaults

2. **Baseline Comparison**:
   - Search git history for memoria configuration changes in past 30 days
   - Review any ChromaDB version upgrades or migrations
   - Check if embedding model or parameters changed

### Phase 2: Vector Space Analysis (Day 1, Afternoon)

1. **Embedding Quality**:
   - Sample 100 random document embeddings and compute statistics (mean, variance, distribution)
   - Check for degenerate embeddings (all zeros, NaN values, extremely similar vectors)
   - Verify embedding dimensionality matches expected model output

2. **Similarity Metric Testing**:
   - Test queries using cosine distance (current default)
   - Test same queries using euclidean distance
   - Test same queries using dot product similarity
   - Compare result diversity and confidence score ranges

### Phase 3: Root Cause Identification (Day 2, Morning)

1. **Hypothesis Testing**:
   - Hypothesis 1: Distance metric misconfigured or changed
   - Hypothesis 2: Vector normalization missing or broken
   - Hypothesis 3: Query embedding process differs from document embedding
   - Hypothesis 4: ChromaDB top_k parameter hardcoded to 1
   - Hypothesis 5: Confidence score calculation error (not using actual distances)

2. **Diagnostic Report**:
   - Document which hypothesis matches observed behavior
   - Identify specific configuration or code causing issue
   - Propose targeted fix with rationale

### Phase 4: Fix Implementation & Validation (Day 2, Afternoon)

1. **Apply Fix**:
   - Implement configuration or code change based on root cause
   - Document what changed and why

2. **Validation**:
   - Re-run 20 test queries and verify success criteria met
   - Test edge cases (empty results, ambiguous queries, short queries)
   - Performance test (ensure <2 second query time maintained)

3. **Documentation**:
   - Update memoria documentation with fix details
   - Add configuration validation checks to prevent regression
   - Create diagnostic scripts for future troubleshooting
