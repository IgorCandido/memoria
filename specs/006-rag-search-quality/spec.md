# Feature Specification: RAG Search Quality & Result Delivery

**Feature Branch**: `006-rag-search-quality`
**Created**: 2026-02-11
**Status**: Draft
**Input**: Fix RAG search returning too few usable results. Address output truncation in caller integrations, improve scoring differentiation, add source-level deduplication, and make result delivery configurable. Currently users see only 1 result even though the system retrieves 5.

## Background

Memoria RAG search currently returns results, but the user experience is degraded by two compounding problems:

1. **Output delivery failure**: When search is invoked through Claude Code's Bash tool or hook wrappers, the rendered output is frequently truncated — users see only 1 result instead of the 5 that were retrieved. This is caused by output size limits, timeout constraints, and verbose formatting that consumes the output budget on the first result.

2. **Search quality issues**: Even when all results are delivered, they cluster around the same narrow score band (0.70–0.73), provide poor differentiation, and often return multiple chunks from the same source document. This makes it hard for the user to find distinct, relevant information across different knowledge areas.

These problems multiply: truncation hides results, and the results that do get through are often duplicates from the same source. The user ends up with effectively one piece of information per search.

### Current State

- Search engine defaults to `limit=5` with hybrid mode (95% semantic, 5% BM25)
- ChromaDB returns correct number of results at the adapter level
- Score compression was previously fixed (hybrid weight changed from 0.7 to 0.95)
- No source-level deduplication exists — same document can appear 3+ times across different chunks
- Output formatting uses Rich panels with borders and padding, consuming significant character budget per result
- BM25 component is a simplified term-frequency approximation, not a true inverted index
- Caller integrations (Bash tool, hooks) impose their own timeouts and output limits

## Dependencies

- Spec 005 (DB-Backed Document Storage) — once documents are stored in Postgres, search metadata and source deduplication can leverage the document registry
- Spec 004 (Configurable Embeddings) — changing embedding models affects score distributions and may require threshold recalibration

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reliable Multi-Result Delivery (Priority: P1)

As a memoria user, I want every search to reliably deliver all requested results to me, so that I can see the full breadth of relevant knowledge rather than having results silently lost to truncation.

**Why this priority**: The most common complaint — users request 5 results but see 1. This is the root cause of the "only 1 result" experience and affects every single search interaction.

**Independent Test**: Run a search query through all caller paths (direct Python, Bash tool, skill invocation). Verify all 5 results are delivered in every path. Measure output size and compare against known caller limits.

**Acceptance Scenarios**:

1. **Given** a search returns 5 results, **When** the output is rendered through the Bash tool path, **Then** all 5 results are visible in the output without truncation
2. **Given** a search returns 5 results, **When** the output is rendered through the skill path, **Then** all 5 results are visible in the output without truncation
3. **Given** output format is set to compact mode, **When** search results are rendered, **Then** each result occupies no more than 4 lines (score, source, excerpt) instead of the current panel-boxed format
4. **Given** a search with `limit=5`, **When** all 5 results are from the same source, **Then** the output clearly indicates they are from the same document rather than appearing as distinct results
5. **Given** a caller timeout of 30 seconds, **When** the search completes within 5 seconds, **Then** the full output is returned before the timeout

---

### User Story 2 - Source-Level Deduplication (Priority: P1)

As a memoria user, I want search results to show information from different source documents, so that I get diverse perspectives rather than multiple chunks from the same file.

**Why this priority**: Returning 3 chunks from the same document in 5 results wastes 60% of the result budget. Users need breadth across their knowledge base.

**Independent Test**: Run a search query that currently returns multiple chunks from the same source. Verify the deduplicated results show one entry per source (highest-scoring chunk), with remaining result slots filled by chunks from different sources.

**Acceptance Scenarios**:

1. **Given** a search that matches 3 chunks from "document_A" and 1 chunk each from "document_B" and "document_C", **When** deduplication is active, **Then** results show the best chunk from each of document_A, document_B, and document_C, plus 2 results from other sources
2. **Given** deduplication is active, **When** only one source matches the query, **Then** multiple chunks from that source are shown (dedup cannot invent new sources)
3. **Given** deduplication is active, **When** the user explicitly requests no deduplication, **Then** all chunks are shown regardless of source overlap
4. **Given** a deduplicated result set, **When** a source's best chunk scores significantly higher than other sources, **Then** that source still appears first (dedup preserves relevance ranking)

---

### User Story 3 - Score Differentiation & Relevance Transparency (Priority: P2)

As a memoria user, I want search scores to meaningfully differentiate between highly relevant and marginally relevant results, so that I can trust the ranking and quickly identify the most valuable result.

**Why this priority**: When all results score 0.70–0.73, the ranking conveys no useful information. Users cannot tell which result is genuinely more relevant.

**Independent Test**: Run 10 diverse queries. For each, verify the score spread between the top and bottom result is at least 0.10, and that the top result is qualitatively more relevant than the bottom result.

**Acceptance Scenarios**:

1. **Given** a search query with clearly varying relevance across documents, **When** results are returned, **Then** the score spread between the highest and lowest result is at least 0.10
2. **Given** a result set, **When** scores are displayed, **Then** each result shows both the raw similarity score and the final combined score, making the ranking transparent
3. **Given** a broad query that matches many documents equally, **When** scores naturally cluster, **Then** a note indicates low differentiation (e.g., "Results have similar relevance")
4. **Given** a highly specific query that matches one document precisely, **When** results are returned, **Then** the top result scores above 0.85 and remaining results score noticeably lower

---

### User Story 4 - Configurable Search Parameters (Priority: P2)

As a memoria power user, I want to configure search behavior (result count, score threshold, deduplication, output format), so that I can tune searches for different use cases.

**Why this priority**: Different callers have different needs — hooks need compact output, interactive users want detailed results, batch operations need raw data.

**Independent Test**: Call `search_knowledge` with each configurable parameter at non-default values. Verify the parameter is respected in the output.

**Acceptance Scenarios**:

1. **Given** a search with `format="compact"`, **When** results are rendered, **Then** output uses a minimal format (no panels, no borders, just score/source/excerpt per line)
2. **Given** a search with `dedup=False`, **When** results are returned, **Then** duplicate source chunks are included as normal
3. **Given** a search with `min_score=0.8`, **When** results below 0.8 exist, **Then** those results are excluded and the actual count is noted (e.g., "3 of 5 results above threshold")
4. **Given** a search with `limit=10`, **When** 10 results are available, **Then** all 10 are returned and rendered

---

### User Story 5 - Improved Keyword Search Component (Priority: P3)

As a memoria user, I want keyword-based search to accurately boost results that contain my exact search terms, so that hybrid search provides better precision than semantic-only search.

**Why this priority**: The current BM25 implementation is a simplified approximation that consistently returns low scores, contributing to the score compression problem. A proper keyword component would improve both relevance and differentiation.

**Independent Test**: Search for an exact phrase that appears verbatim in a known document. Verify the keyword component boosts that document's score above documents that are only semantically similar.

**Acceptance Scenarios**:

1. **Given** a query containing an exact phrase from a document, **When** hybrid search runs, **Then** that document scores higher than it would with semantic-only search
2. **Given** a query with technical terms (e.g., "ChromaDB healthcheck TCP"), **When** hybrid search runs, **Then** documents containing those exact terms rank higher than semantically similar documents without the terms
3. **Given** the current corpus (~293 docs, ~17K chunks), **When** keyword scoring runs, **Then** it completes within 500ms (no full-corpus scan per query)

---

### Edge Cases

- What happens when the output size exceeds the Bash tool's character limit? (Switch to compact format automatically, or return a file path to the full results)
- What happens when deduplication reduces results below the requested limit? (Fill remaining slots with next-best chunks from already-represented sources, noting they are additional chunks)
- What happens when all results score below the minimum threshold? (Return results anyway with a note that confidence is low, rather than returning empty)
- What happens when a search times out at the embedding step? (Return cached results if available, or a clear timeout message rather than partial output)
- What happens when two chunks from the same source have very different content? (Deduplication should have an option to allow multiple chunks from one source if they are semantically dissimilar)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST deliver all requested results through every caller path (direct Python, Bash tool, skill invocation) without silent truncation
- **FR-002**: System MUST provide a compact output format that renders each result in no more than 4 lines (score, source, excerpt) instead of the current panel-boxed format
- **FR-003**: System MUST perform source-level deduplication by default, showing at most one chunk per source document and filling remaining slots with chunks from other sources
- **FR-004**: System MUST allow deduplication to be disabled via a parameter for callers that need all chunks
- **FR-005**: System MUST produce a minimum score spread of 0.10 between the most and least relevant results for queries with varying relevance across the corpus
- **FR-006**: System MUST expose configurable search parameters: result limit, minimum score threshold, deduplication toggle, and output format
- **FR-007**: System MUST detect when output would exceed the caller's known size limit and automatically switch to compact format
- **FR-008**: System MUST return results even when all scores fall below the configured threshold, with a low-confidence indicator, rather than returning empty
- **FR-009**: System MUST display both raw similarity score and final combined score for each result to make ranking transparent
- **FR-010**: System MUST improve the keyword search component to meaningfully contribute to hybrid scoring, ensuring exact term matches boost relevance
- **FR-011**: System MUST complete the full search pipeline (embedding + retrieval + scoring + rendering) within 5 seconds for the standard corpus size

### Non-Functional Requirements

- **NFR-001**: Compact format output for 5 results MUST fit within 2000 characters to stay within common tool output limits
- **NFR-002**: Search quality improvements MUST NOT increase per-query latency by more than 500ms compared to the current implementation
- **NFR-003**: Deduplication logic MUST NOT require additional database queries beyond the existing search — it operates on the result set in memory
- **NFR-004**: All search parameter changes MUST be backward-compatible — existing callers using default parameters see improved but not broken behavior

### Key Entities

- **SearchResult**: Extended to include raw score, combined score, source document identifier, dedup flag, and chunk position within source.
- **SearchConfig**: New configuration object for search parameters — limit, min_score, dedup mode, output format, hybrid weight.
- **OutputFormat**: Enumeration of rendering modes — detailed (current panels), compact (4-line per result), raw (JSON for programmatic consumption).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users see all requested results (default 5) in every caller path — zero truncation incidents in standard usage
- **SC-002**: No more than 1 result per source document in the default deduplicated result set (when multiple sources match)
- **SC-003**: Score spread between highest and lowest result is at least 0.10 for 80% of queries against the standard corpus
- **SC-004**: Compact output for 5 results fits within 2000 characters
- **SC-005**: End-to-end search latency (query to rendered output) remains under 5 seconds for the standard corpus
- **SC-006**: Exact-phrase searches rank the matching document in the top 2 results when using hybrid mode
- **SC-007**: User satisfaction with search results improves — measured by reduction in repeated/rephrased queries for the same information

## Assumptions

- The primary caller paths are: direct Python import, Claude Code Bash tool invocation, and the memoria skill entry point
- The Bash tool output limit in Claude Code is approximately 30,000 characters, but effective visibility is lower due to rendering
- The current corpus (~293 docs, ~17K chunks) is representative of the expected search workload
- The current distance metric is cosine distance, converted to similarity via `1 - (distance / 2)`
- Source deduplication uses the `source` metadata field already present in all indexed documents
- The BM25 improvement will use an in-memory term index built at search time from the candidate set, not a persistent inverted index
- Spec 005 (DB-backed storage) may later provide a persistent keyword index, but this spec's improvements must work without it
