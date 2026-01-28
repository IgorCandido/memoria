# ChromaDB Search Quality Investigation Report

**Feature**: 001-chroma-search-fix
**Investigation Start**: 2026-01-24
**Status**: Phase 0 - Investigation Required

## Executive Summary

**Investigation Complete**: 2026-01-28

**Problem**: ChromaDB search queries were reported to return only 1 result with narrow confidence scores (0.4-0.6) instead of multiple relevant results with graduated scores (0.2-0.9).

**Key Finding**: The "single result" claim in the spec was incorrect. Testing shows ALL queries return 10 results (as requested), but the REAL problem is **severe score compression** in hybrid search mode.

**Root Cause**: Hybrid search mode (70% semantic + 30% BM25) is compressing confidence scores from 0.75-0.79 range (pure semantic) down to 0.54-0.56 range. The BM25 keyword component consistently returns low/zero scores, which when mixed with semantic scores, dampens the overall confidence and eliminates score differentiation.

**Proposed Fix**: Either (1) disable hybrid mode and use pure semantic search, (2) adjust hybrid weighting to 90/10, or (3) fix BM25 scoring normalization before mixing with semantic scores

---

## Current Behavior Baseline

*[Task 0.1: Document exact current behavior with test queries]*

### Test Query Results

*To be populated with baseline test results showing:*
- Query text
- Number of results returned
- Confidence scores
- Raw ChromaDB distances
- Query embedding statistics

### Expected Behavior

Based on spec.md requirements:
- Queries should return 3-10 results when relevant documents exist
- Confidence scores should span 0.2-0.9 range (not cluster at 0.4-0.6)
- High-relevance queries should score ≥0.7
- Semantic queries should retrieve conceptually related documents

---

## Vector Space Analysis

*[Task 0.2: Analyze vector space characteristics]*

### ChromaDB Collection Metadata

*To be populated with:*
- Distance metric configuration
- Embedding dimensions
- Index type and parameters
- Collection statistics

### Embedding Quality Analysis

*To be populated with:*
- Sample embedding statistics (mean, variance, norms)
- Degenerate vector check results
- Distribution visualization
- Comparison with expected embedding model output

### Query Embedding Analysis

*To be populated with:*
- Query embedding generation process review
- Dimensionality verification
- Normalization check

---

## Distance Calculation Analysis

*[Task 0.3: Verify distance-to-similarity conversion]*

### ChromaDB Distance Formula Review

**Current Implementation** (`memoria/adapters/chromadb/chromadb_adapter.py:147-148`):
```python
similarity = max(0.0, min(1.0, 1.0 - (distance / 2.0)))
```

**Formula Analysis**:
- Assumes ChromaDB returns cosine distance in [0, 2] range
- Converts distance=0 (identical) → similarity=1.0 ✓
- Converts distance=2 (opposite) → similarity=0.0 ✓

**Questions to Answer**:
1. Does ChromaDB actually return cosine distance or cosine similarity?
2. Is the [0, 2] range assumption correct for ChromaDB's implementation?
3. Are there edge cases where this formula produces incorrect scores?

### Known Vector Testing

*To be populated with test results:*
- Identical vectors: expected distance ≈ 0, observed ___
- Orthogonal vectors: expected distance ≈ 1.0, observed ___
- Opposite vectors: expected distance ≈ 2.0, observed ___

### ChromaDB Query Parameters

**Current Implementation** (`memoria/adapters/chromadb/chromadb_adapter.py:128-131`):
```python
results = self._collection.query(
    query_embeddings=[query_embedding],
    n_results=k,
)
```

**Questions to Answer**:
1. Is `n_results=k` being correctly passed (not hardcoded)?
2. Does ChromaDB respect the `n_results` parameter?
3. Are there additional parameters needed (e.g., distance threshold)?

---

## Search Algorithm Analysis

*[Task 0.4: Analyze hybrid search behavior]*

### Search Mode Comparison

*To be populated with test results comparing:*
- Semantic search only (`mode="semantic"`)
- Keyword search only (`mode="bm25"`)
- Hybrid search (`mode="hybrid"`)

For each mode, document:
- Number of results returned
- Score range and distribution
- Example results for test queries

### Hybrid Search Algorithm Review

**Current Implementation** (`memoria/adapters/search/search_engine_adapter.py:135-184`):

Key steps:
1. Semantic search retrieves `limit * 2` candidates
2. Keyword search retrieves `limit * 2` candidates
3. Scores combined via weighted average (70% semantic, 30% keyword)
4. Results sorted and sliced to top `limit`

**Questions to Answer**:
1. Are semantic/keyword searches each returning only 1 result?
2. Is the scoring combination eliminating results?
3. Is there unexpected deduplication?

---

## Configuration History

*[Task 0.5: Identify configuration changes]*

### Git History Analysis

*To be populated with:*
- Recent commits to ChromaDB adapter
- Recent commits to search engine adapter
- Recent commits to skill_helpers.py
- Timeline of changes

### ChromaDB Version History

*To be populated with:*
- Current ChromaDB version
- Previous ChromaDB versions
- API changes between versions

### ChromaDB Server Configuration

*To be populated with:*
- Docker container configuration review
- Distance metric settings
- HNSW parameters (if applicable)
- Any non-default settings

---

## Root Cause Analysis

*[Task 0.6: Synthesize findings and identify root cause]*

### Hypothesis Testing Results

| Hypothesis | Result | Evidence | Confidence |
|------------|--------|----------|------------|
| H1: Distance-to-similarity formula incorrect | ❌ REJECTED | Formula works correctly for known vectors (identical→1.0, related→0.75) | HIGH |
| H2: ChromaDB returns similarity, not distance | ❌ REJECTED | ChromaDB confirmed returning cosine distance in [0,2] range | HIGH |
| H3: ChromaDB `n_results` parameter not working | ❌ REJECTED | All 20 test queries returned exactly 10 results as requested | HIGH |
| H4: Vector normalization missing | ❌ REJECTED | Collection health check shows perfect normalization (norm=1.0±0.0) | HIGH |
| H5: Vector space collapsed (all similar) | ⚠️ PARTIAL | Vector space density 0.49 is reasonable, BUT ChromaDB queries return very narrow distance range (0.49-0.51) | MEDIUM |
| H6: Hybrid search filtering to 1 result | ❌ REJECTED (but related) | Hybrid returns 10 results, but DOES compress scores vs pure semantic | HIGH |
| **H7: Hybrid BM25 component dampening scores** | ✅ **CONFIRMED** | Semantic mode: 0.75-0.79 scores, Hybrid mode: 0.54-0.56 scores (30% penalty) | **HIGH** |

### Confirmed Root Cause

**Primary Cause**: Hybrid search mode's BM25 keyword component is consistently returning low/zero scores for most documents, which when mixed with high semantic scores (70/30 weighting), severely compresses the confidence score range and lowers overall scores.

**Contributing Factors**:
1. BM25 scoring lacks normalization before mixing with semantic scores
2. Many documents lack exact keyword matches, resulting in BM25 score ≈ 0
3. 30% weight for BM25 is too high given the score distribution mismatch

**Supporting Evidence**:
- T006: Distance formula validated correct with known vectors
- T007: Baseline test shows 100% queries return 10 results (not 1!)
- T008: Collection health perfect (embeddings normalized, no degenerate vectors)
- T009: **SMOKING GUN** - Semantic mode scores 0.75-0.79, Hybrid mode 0.54-0.56
- T010: Fresh repo, no historical configuration drift

---

## Proposed Fix

### Option 1: Disable Hybrid Mode (RECOMMENDED - Simplest)

**Change**: Update `memoria/skill_helpers.py` line 91 to use pure semantic search:
```python
# Before:
results = search_engine.search(query=query, limit=limit, mode="hybrid" if mode == "hybrid" else "semantic")

# After:
results = search_engine.search(query=query, limit=limit, mode="semantic")
```

**Rationale**:
- Semantic search alone produces good scores (0.75-0.79 range)
- Eliminates BM25 dampening effect immediately
- No risk of introducing new bugs
- Users can still request "hybrid" mode but it will use semantic internally

**Pros**: Simple, safe, immediate fix
**Cons**: Loses potential benefit of keyword matching (though testing shows BM25 not helping)

### Option 2: Adjust Hybrid Weighting (RECOMMENDED - Better Long-term)

**Change**: Update `memoria/adapters/search/search_engine_adapter.py` line 24 (constructor):
```python
# Before:
self._hybrid_weight = hybrid_weight  # Default 0.7 (70% semantic, 30% BM25)

# After:
self._hybrid_weight = 0.95  # 95% semantic, 5% BM25
```

**Rationale**:
- Preserves hybrid search capability
- Reduces BM25 impact from 30% to 5%
- Expected score range: 0.71-0.75 (vs 0.54-0.56 currently)
- Still allows BM25 to provide keyword boost when relevant

**Pros**: Maintains hybrid functionality, score improvement, configurable
**Cons**: Still has some dampening effect (though much reduced)

### Option 3: Normalize BM25 Scores Before Mixing (COMPLEX)

**Change**: Update hybrid search algorithm in `memoria/adapters/search/search_engine_adapter.py` lines 163-172 to normalize BM25 scores to match semantic score distribution before combining.

**Rationale**: Addresses root cause of score mismatch directly

**Pros**: True hybrid search with proper score mixing
**Cons**: Complex, requires empirical calibration, higher risk

### Alternative Approaches Considered

**Rejected: Fix BM25 implementation**
- BM25 is working as designed (returning 0 for no keyword matches)
- Problem is the mixing strategy, not BM25 itself

**Rejected: Increase n_results to compensate**
- Doesn't address score compression issue
- Already returning 10 results as requested

---

## Validation Plan

*[To be completed after fix design]*

### Test Cases

*Specific tests to verify fix works*

### Success Metrics

*How to measure fix effectiveness*

### Regression Prevention

*Tests to ensure fix doesn't break existing functionality*

---

## Investigation Timeline

- **Phase 0 Start**: 2026-01-24
- **Investigation Execution**: 2026-01-28
- **Task 0.3 (Distance Audit - T006)**: ✅ COMPLETE - Formula validated correct
- **Task 0.1 (Baseline - T007)**: ✅ COMPLETE - 20 queries tested, all return 10 results
- **Task 0.2 (Vector Analysis - T008)**: ✅ COMPLETE - Collection healthy, vectors normalized
- **Task 0.4 (Search Algorithm - T009)**: ✅ COMPLETE - **Root cause identified**: Hybrid mode compression
- **Task 0.5 (Config History - T010)**: ✅ COMPLETE - Fresh repo, no historical drift
- **Task 0.6 (Root Cause - T011)**: ✅ COMPLETE - H7 confirmed: BM25 dampening scores
- **Phase 0 Complete**: 2026-01-28 (2 hours total investigation time)

**Diagnostic Outputs Generated**:
- `baseline_results.csv` - 20 test queries with detailed metrics
- `collection_stats.json` - Collection health metrics
- `test_distance_formula.py` output - Formula validation results
- `compare_search_modes.py` output - Semantic vs Hybrid comparison

---

## Next Steps

1. **Execute Task 0.3** (Distance Metric Audit) - Most likely to reveal issue quickly
2. Execute remaining investigation tasks based on Task 0.3 findings
3. Complete root cause analysis
4. Design and document fix
5. Proceed to Phase 1 (Fix Implementation Design)

---

**Note**: This is a living document. Update each section as investigation progresses. All findings should be evidence-based with specific data/logs/test results.
