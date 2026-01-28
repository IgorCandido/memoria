# Implementation Plan: ChromaDB Search Quality Investigation & Fix

**Branch**: `001-chroma-search-fix` | **Date**: 2026-01-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-chroma-search-fix/spec.md`

## Summary

Investigate and fix ChromaDB search quality degradation where queries return only a single result with narrow confidence scores (0.4-0.6) instead of multiple relevant results with graduated scores (0.2-0.9). The fix will analyze vector space characteristics, distance metrics, and configuration to restore proper multi-result semantic search while maintaining backward compatibility with the existing `search_knowledge` interface.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: ChromaDB >=0.4.0, sentence-transformers >=2.2.0, pytest (for testing)
**Storage**: ChromaDB HTTP mode (localhost:8001), existing collection "memoria" with 2837 docs, 1793+ chunks
**Testing**: pytest with existing test suite (tests/adapters/chromadb/, tests/adapters/search/)
**Target Platform**: macOS (development), Linux (production Docker container)
**Project Type**: Single project - Python library with CLI interface (skill_helpers.py)
**Performance Goals**: Query completion <2 seconds for 5000 documents, maintain current throughput
**Constraints**:
- Must preserve existing embeddings (no re-indexing unless corrupt)
- Backward compatible with `search_knowledge(query, mode, expand, limit)` interface
- Must not break existing MCP server integration or skill interface
**Scale/Scope**:
- 2837 documents currently indexed
- 1793+ embedding chunks
- All-MiniLM-L6-v2 embedding model (384 dimensions)
- Cosine distance metric (default ChromaDB)

## Constitution Check

**Status**: No constitution file found in `.specify/memory/constitution.md` (template placeholder only)

**Assumed Principles** (based on memoria architecture):
- ✅ **Hexagonal Architecture**: Clear separation between ports (interfaces) and adapters (implementations)
- ✅ **Test-First**: Comprehensive test coverage exists (ports, adapters, integration, acceptance)
- ✅ **Single Responsibility**: Each adapter handles one concern (search, vector store, embeddings)

**Gates**:
- Investigation must complete before implementation (Phase 0 → Phase 1)
- Root cause must be identified before fix design (diagnostic report required)
- All existing tests must pass after fix (regression prevention)

## Project Structure

### Documentation (this feature)

```text
specs/001-chroma-search-fix/
├── plan.md              # This file
├── research.md          # Phase 0: Investigation findings and root cause analysis
├── data-model.md        # Phase 1: Diagnostic data structures (if needed)
├── quickstart.md        # Phase 1: How to validate the fix
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code (repository root)

```text
memoria/
├── skill_helpers.py               # HIGH-LEVEL API - Main entry point for search_knowledge()
├── adapters/
│   ├── chromadb/
│   │   └── chromadb_adapter.py    # VectorStorePort implementation (SEARCH METHOD - line 116)
│   ├── search/
│   │   └── search_engine_adapter.py # SearchEnginePort implementation (HYBRID SEARCH - line 135)
│   └── sentence_transformers/
│       └── sentence_transformer_adapter.py # EmbeddingGeneratorPort implementation
├── domain/
│   ├── entities.py                # Document, SearchResult entities
│   ├── value_objects.py           # Embedding, QueryTerms value objects
│   └── ports/
│       ├── vector_store.py        # VectorStorePort protocol
│       └── search_engine.py       # SearchEnginePort protocol
└── compatibility/
    └── raggy_facade.py            # Legacy raggy.py interface (if used)

tests/
├── adapters/
│   ├── chromadb/
│   │   └── test_chromadb_adapter.py     # CRITICAL - Vector store tests
│   └── search/
│       └── test_search_engine_adapter.py # CRITICAL - Search engine tests
├── integration/
│   └── [integration tests]              # End-to-end search tests
└── test_skill_helpers.py                # HIGH-LEVEL API tests

docs/
└── [2837 markdown files]                # Indexed knowledge base
```

**Structure Decision**: Single project architecture with hexagonal/ports-and-adapters pattern. Investigation and fix will focus on two critical components:

1. **ChromaDBAdapter.search()** (line 116-171): Converts ChromaDB distance to similarity score
2. **SearchEngineAdapter._hybrid_search()** (line 135-184): Combines semantic and keyword search

## Complexity Tracking

N/A - No constitution violations. This is a bug fix within existing architecture.

---

## Phase 0: Investigation & Root Cause Analysis

### Objective

Identify why ChromaDB search returns only 1 result with clustered confidence scores (0.4-0.6) instead of multiple results with graduated scores.

### Investigation Tasks

#### Task 0.1: Current Behavior Baseline

**Goal**: Document exact current behavior with test queries

**Steps**:
1. Create diagnostic script: `specs/001-chroma-search-fix/diagnostics/baseline_test.py`
2. Execute 20 diverse test queries against current system:
   - Exact match queries (e.g., "claude loop protocol")
   - Semantic queries (e.g., "agent catalog")
   - Synonym queries (e.g., "query tracking" vs "RAG compliance")
   - Short queries (1-2 words)
   - Long queries (full sentences)
3. Log for each query:
   - Number of results returned
   - Confidence scores for all results
   - ChromaDB raw distances
   - Query embedding statistics

**Expected Output**:
- `research.md` section: "Current Behavior Baseline"
- CSV file: `diagnostics/baseline_results.csv`

#### Task 0.2: ChromaDB Collection Analysis

**Goal**: Analyze vector space characteristics

**Steps**:
1. Query ChromaDB collection metadata:
   - Distance metric (cosine, euclidean, L2?)
   - Embedding dimensions (should be 384 for all-MiniLM-L6-v2)
   - Index type (HNSW parameters if applicable)
2. Sample 100 random embeddings:
   - Check for degenerate vectors (all zeros, NaNs, identical vectors)
   - Compute distribution statistics (mean, variance, L2 norms)
   - Visualize using PCA/t-SNE if possible
3. Test query embedding generation:
   - Generate embeddings for test queries
   - Compare dimensionality and normalization with document embeddings

**Expected Output**:
- `research.md` section: "Vector Space Analysis"
- JSON file: `diagnostics/collection_stats.json`

#### Task 0.3: Distance Metric & Similarity Calculation Audit

**Goal**: Verify distance-to-similarity conversion is correct

**Steps**:
1. Review `ChromaDBAdapter.search()` line 147-148:
   ```python
   similarity = max(0.0, min(1.0, 1.0 - (distance / 2.0)))
   ```
   - Is this formula correct for cosine distance?
   - ChromaDB cosine distance range: [0, 2] (0=identical, 2=opposite)
   - Expected similarity range: [0, 1] (0=unrelated, 1=identical)
   - Current formula converts distance=0 → similarity=1.0 ✓
   - Current formula converts distance=2 → similarity=0.0 ✓
   - **BUT**: Does ChromaDB actually return cosine distance or cosine similarity?

2. Test with known vectors:
   - Create two identical vectors → expect distance ≈ 0, similarity ≈ 1.0
   - Create two orthogonal vectors → expect distance ≈ 1.0, similarity ≈ 0.5
   - Create two opposite vectors → expect distance ≈ 2.0, similarity ≈ 0.0

3. Check ChromaDB query parameters:
   - Review `_collection.query()` call (line 128-131)
   - Verify `n_results=k` is correctly passed (not hardcoded to 1)
   - Check if distance metric can be explicitly specified

**Expected Output**:
- `research.md` section: "Distance Calculation Analysis"
- Hypothesis: Is the distance-to-similarity formula incorrect?

#### Task 0.4: Search Engine Hybrid Algorithm Review

**Goal**: Analyze why hybrid search might be filtering to 1 result

**Steps**:
1. Review `SearchEngineAdapter._hybrid_search()` line 135-184:
   - Semantic search retrieves `limit * 2` results (line 142)
   - Keyword search retrieves `limit * 2` results (line 145)
   - Scores are combined with weighted average (line 167-170)
   - Results sorted and sliced to `[:limit]` (line 183)
2. Check if any intermediate steps could reduce result count:
   - Are semantic or keyword searches returning only 1 result?
   - Is the hybrid scoring eliminating results?
   - Is there a deduplication issue?

3. Test each search mode independently:
   - Run same query with `mode="semantic"` only
   - Run same query with `mode="bm25"` only
   - Run same query with `mode="hybrid"`
   - Compare result counts and scores

**Expected Output**:
- `research.md` section: "Search Algorithm Analysis"
- Hypothesis: Which search component is the bottleneck?

#### Task 0.5: Configuration Drift Analysis

**Goal**: Identify if configuration changed recently

**Steps**:
1. Review git history for memoria:
   - `git log --since="30 days ago" --oneline -- memoria/adapters/chromadb/`
   - `git log --since="30 days ago" --oneline -- memoria/adapters/search/`
   - `git log --since="30 days ago" --oneline -- memoria/skill_helpers.py`
2. Check for ChromaDB version changes:
   - Review `requirements.txt` history
   - Check if ChromaDB API changed between versions
3. Review ChromaDB server configuration (Docker):
   - Check if distance metric setting exists
   - Verify HNSW parameters if applicable

**Expected Output**:
- `research.md` section: "Configuration History"
- Timeline of changes that could affect search behavior

#### Task 0.6: Hypothesis Testing & Root Cause Identification

**Goal**: Synthesize findings and identify root cause

**Hypotheses to Test**:

1. **H1: Distance-to-similarity formula is incorrect**
   - **Test**: Manually compute cosine similarity for known query-doc pair, compare with ChromaDB distance
   - **If true**: Fix formula in `ChromaDBAdapter.search()` line 148

2. **H2: ChromaDB returns similarity, not distance**
   - **Test**: Check ChromaDB documentation and test with known vectors
   - **If true**: Remove or invert conversion formula

3. **H3: ChromaDB query `n_results` parameter not working**
   - **Test**: Add logging to verify `k` value passed to `_collection.query()`
   - **If true**: Investigate ChromaDB client bug or API misuse

4. **H4: Vector normalization missing**
   - **Test**: Check if embeddings are normalized (L2 norm = 1.0)
   - **If true**: Normalize embeddings before adding to ChromaDB

5. **H5: All embeddings are too similar (vector space collapse)**
   - **Test**: Compute pairwise distances between random sample of 100 docs
   - **If true**: Investigate embedding model or chunking strategy

6. **H6: Hybrid search is filtering to 1 result**
   - **Test**: Compare result counts for semantic-only vs hybrid search
   - **If true**: Fix hybrid search algorithm in `SearchEngineAdapter`

**Expected Output**:
- `research.md` section: "Root Cause Analysis"
- Confirmed hypothesis with supporting evidence
- Proposed fix with rationale

### Phase 0 Deliverable

**File**: `specs/001-chroma-search-fix/research.md`

**Structure**:
```markdown
# ChromaDB Search Quality Investigation Report

## Executive Summary
[One paragraph: root cause found, proposed fix]

## Current Behavior Baseline
[Test query results showing single-result problem]

## Vector Space Analysis
[Embedding statistics, dimensionality, distribution]

## Distance Calculation Analysis
[Formula review, ChromaDB API behavior]

## Search Algorithm Analysis
[Semantic vs keyword vs hybrid comparison]

## Configuration History
[Recent changes that could affect behavior]

## Root Cause Analysis
[Confirmed hypothesis with evidence]

### Hypothesis Testing Results
| Hypothesis | Result | Evidence |
|------------|--------|----------|
| H1: Formula incorrect | CONFIRMED/REJECTED | [data] |
| H2: Distance vs similarity | CONFIRMED/REJECTED | [data] |
| ... | ... | ... |

## Proposed Fix
[Specific code changes with rationale]

## Validation Plan
[How to verify fix works]
```

---

## Phase 1: Fix Design & Validation Planning

### Objective

Design the fix based on root cause analysis and plan validation approach.

### Design Tasks

#### Task 1.1: Fix Implementation Design

**Based on root cause** (example scenarios):

**Scenario A: Distance-to-similarity formula incorrect**
- **Change**: Update `ChromaDBAdapter.search()` line 148
- **Before**: `similarity = max(0.0, min(1.0, 1.0 - (distance / 2.0)))`
- **After**: Correct formula based on ChromaDB distance type
- **Files Modified**: `memoria/adapters/chromadb/chromadb_adapter.py`

**Scenario B: Need to request more results from ChromaDB**
- **Change**: Increase `k` parameter or change ChromaDB distance threshold
- **Files Modified**: `memoria/adapters/chromadb/chromadb_adapter.py`

**Scenario C: Hybrid search algorithm issue**
- **Change**: Fix result combination logic in `SearchEngineAdapter._hybrid_search()`
- **Files Modified**: `memoria/adapters/search/search_engine_adapter.py`

**Scenario D: Vector normalization missing**
- **Change**: Normalize embeddings in `SentenceTransformerAdapter` or before adding to ChromaDB
- **Files Modified**: `memoria/adapters/sentence_transformers/sentence_transformer_adapter.py`

#### Task 1.2: Backward Compatibility Analysis

**Affected Interfaces**:
1. `search_knowledge(query, mode, expand, limit)` in `skill_helpers.py`
   - **Change**: None (interface unchanged)
   - **Internal**: Different results returned (multiple vs single)

2. `SearchEngineAdapter.search()` in domain/ports
   - **Change**: None (protocol unchanged)
   - **Internal**: Score range may change (0.2-0.9 vs 0.4-0.6)

3. `ChromaDBAdapter.search()` in domain/ports
   - **Change**: None (protocol unchanged)
   - **Internal**: Similarity calculation may change

**Breaking Change Analysis**: None expected - all changes are internal fixes

#### Task 1.3: Test Strategy Design

**Test Levels**:

1. **Unit Tests** (ports and adapters):
   - `tests/adapters/chromadb/test_chromadb_adapter.py`
     - Add test: `test_search_returns_multiple_results`
     - Add test: `test_similarity_scores_graduated`
     - Add test: `test_high_relevance_scores_above_threshold`
   - `tests/adapters/search/test_search_engine_adapter.py`
     - Add test: `test_hybrid_search_multiple_results`
     - Add test: `test_semantic_search_score_range`

2. **Integration Tests**:
   - `tests/integration/test_search_quality.py` (NEW FILE)
     - Test end-to-end search with real ChromaDB instance
     - Verify multiple results returned
     - Verify score distribution

3. **Acceptance Tests**:
   - `tests/acceptance/test_search_acceptance.py` (NEW FILE)
     - Test all user stories from spec.md
     - Verify success criteria (SC-001 through SC-007)

**Test Data**:
- Use existing docs/ directory (2837 documents)
- Create small test collection with known query-document pairs
- Test queries from spec.md user stories

#### Task 1.4: Performance Validation Planning

**Metrics to Track**:
1. Query latency (p50, p95, p99)
2. Result count distribution (1, 2-5, 6-10, >10 results)
3. Confidence score distribution (min, max, mean, std dev)
4. ChromaDB query time vs total search time

**Benchmarking**:
- Run 100 test queries before and after fix
- Compare performance metrics
- Ensure <2 second query time maintained (SC-006)

#### Task 1.5: Diagnostic Tools Design

**Tools to Create**:

1. `specs/001-chroma-search-fix/diagnostics/search_debugger.py`
   - Interactive tool to run queries and inspect results
   - Shows: query embedding, raw ChromaDB distances, similarity scores, result count
   - Usage: `python search_debugger.py "query text"`

2. `specs/001-chroma-search-fix/diagnostics/validate_fix.py`
   - Automated validation script
   - Runs 20 test queries from spec.md
   - Checks success criteria (SC-001 through SC-007)
   - Outputs pass/fail report

3. `memoria/adapters/chromadb/diagnostics.py` (NEW FILE)
   - Functions to inspect collection health
   - Check embedding dimensions, vector norms, distance distributions
   - Can be imported for troubleshooting

### Phase 1 Deliverables

#### File: `specs/001-chroma-search-fix/data-model.md`

```markdown
# ChromaDB Search Diagnostic Data Model

## Diagnostic Entities

### QueryDiagnostic
- query_text: str
- query_embedding: list[float]
- embedding_norm: float
- timestamp: datetime

### SearchDiagnostic
- query: QueryDiagnostic
- num_results: int
- raw_distances: list[float]
- similarity_scores: list[float]
- execution_time_ms: float
- search_mode: str

### CollectionHealth
- total_documents: int
- embedding_dimensions: int
- distance_metric: str
- sample_embedding_norms: list[float]
- vector_space_density: float
```

#### File: `specs/001-chroma-search-fix/quickstart.md`

```markdown
# ChromaDB Search Fix - Validation Quickstart

## Prerequisites

- Python 3.11+
- ChromaDB running on localhost:8001
- Memoria collection with indexed documents

## Quick Validation

### 1. Run Diagnostic Tests

```bash
cd specs/001-chroma-search-fix/diagnostics
python validate_fix.py
```

Expected output:
```
✅ SC-001: 90% of queries return 5+ results (PASS: 95%)
✅ SC-002: Confidence scores span ≥0.4 range (PASS: 0.52)
✅ SC-003: High-relevance queries score ≥0.7 (PASS: 0.78)
...
```

### 2. Interactive Search Debugging

```bash
python search_debugger.py "claude loop protocol"
```

Expected output:
```
Query: "claude loop protocol"
Query embedding norm: 1.0000
Search mode: hybrid

Results (10 found):
  1. Score: 0.85 | Distance: 0.30 | docs/claude-loop-protocol.md
  2. Score: 0.72 | Distance: 0.56 | docs/agent-catalog.md
  ...
```

### 3. Run Full Test Suite

```bash
pytest tests/adapters/chromadb/ tests/adapters/search/ -v
pytest tests/integration/test_search_quality.py -v
pytest tests/acceptance/test_search_acceptance.py -v
```

All tests should pass.

## Troubleshooting

### Still getting single results?

1. Check ChromaDB is running: `curl http://localhost:8001/api/v1/heartbeat`
2. Verify collection exists: `python -c "from memoria.skill_helpers import get_stats; print(get_stats())"`
3. Run diagnostics: `python search_debugger.py "test query" --verbose`

### Scores still clustered 0.4-0.6?

1. Check embedding normalization: `python diagnostics/check_embeddings.py`
2. Verify distance metric: `python diagnostics/check_chromadb_config.py`
3. Review fix implementation in `memoria/adapters/chromadb/chromadb_adapter.py`
```

#### File: `specs/001-chroma-search-fix/contracts/`

N/A - This is an internal fix, no external API contracts needed.

---

## Phase 2: Implementation (Not part of `/speckit.plan`)

*Phase 2 (implementation) will be handled by `/speckit.tasks` and `/speckit.implement` commands.*

*This plan document ends after Phase 1 design, as specified in the skill workflow.*

---

## Success Criteria Mapping

| Success Criterion | Validation Method | Target | Current |
|-------------------|-------------------|--------|---------|
| SC-001: 90% queries return 5+ results | Automated test with 100 diverse queries | ≥90% | 0% (all return 1) |
| SC-002: Score range ≥0.4 | Measure max-min score across results | ≥0.4 | ~0.2 (0.4-0.6) |
| SC-003: High-relevance ≥0.7 | Test exact match queries | ≥0.7 | ~0.5 |
| SC-004: Semantic retrieval in top 5 | Test synonym/paraphrase queries | ≥80% | Unknown |
| SC-005: Report within 2 days | Phase 0 completion | 2 days | TBD |
| SC-006: Query time <2 seconds | Performance benchmark | <2s | ~1s (current) |
| SC-007: User satisfaction | Post-fix feedback collection | Improved | N/A |

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Root cause is embeddings quality | Medium | High | Can re-index with better chunking if needed |
| ChromaDB API behavior changed | Low | High | Pin to known-good version, review changelog |
| Fix breaks existing functionality | Low | High | Comprehensive test suite, gradual rollout |
| Performance degrades | Low | Medium | Benchmark before/after, optimize if needed |
| Vector space collapsed (all similar) | Medium | Critical | May require re-embedding with better model |

---

## Next Steps

1. **Execute Phase 0 Investigation** (research.md):
   - Run diagnostic tasks 0.1 through 0.6
   - Identify root cause
   - Document findings in `research.md`

2. **Execute Phase 1 Design** (this phase):
   - Complete based on Phase 0 findings
   - Fill in diagnostic tools
   - Create quickstart guide
   - Generate test strategy

3. **Proceed to `/speckit.tasks`**:
   - Break down implementation into tasks
   - Create dependency-ordered tasks.md
   - Ready for `/speckit.implement`

---

**Agent Note**: When executing Phase 0 investigation, start with Task 0.3 (distance metric audit) as it's most likely to reveal the issue quickly. ChromaDB distance-to-similarity conversion is a common source of confusion.
