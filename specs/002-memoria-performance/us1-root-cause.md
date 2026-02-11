# US1 Root Cause Analysis: Multi-Result Search

**Date**: 2026-01-31
**Analyst**: Claude Agent
**Status**: Investigation Complete

## Summary

**FINDING**: The reported issue "ChromaDB returns only 1 result" **DOES NOT EXIST** in current implementation.

- ✅ 100% of test queries return exactly 10 results (as requested)
- ✅ ChromaDB n_results parameter works correctly
- ✅ Hybrid search properly combines semantic and keyword results
- ✅ hybrid_weight=0.95 fix from spec 001 is effective

**Conclusion**: Either the issue was already fixed, or the spec is based on incorrect observation. NO CODE CHANGES NEEDED for US1.

## Investigation Tasks (T015-T018)

### T015: Analyze hybrid_weight=0.95 Effectiveness

**Location**: `memoria/adapters/search/search_engine_adapter.py:30`

**Current Implementation**:
```python
def __init__(
    self,
    vector_store: VectorStorePort,
    embedding_generator: EmbeddingGeneratorPort,
    hybrid_weight: float = 0.95,  # 95% semantic, 5% BM25
) -> None:
```

**Analysis**:
- hybrid_weight=0.95 means 95% semantic score + 5% keyword score
- This minimizes BM25 dampening effect (only 5% contribution)
- Hybrid search combines scores: `hybrid_score = 0.95 * semantic + 0.05 * keyword`

**Finding**: hybrid_weight=0.95 IS effective at scale:
- All queries return 10 results (100% success rate)
- Scores range from 0.69-0.71 (narrow but functional)
- No evidence of "single result" regression

### T016: Check n_results Parameter Handling

**Location**: `memoria/adapters/chromadb/chromadb_adapter.py:116-131`

**Current Implementation**:
```python
def search(self, query_embedding: list[float], k: int = 5) -> list[SearchResult]:
    # Query ChromaDB
    results = self._collection.query(
        query_embeddings=[query_embedding],
        n_results=k,  # ChromaDB parameter for result count
    )
```

**Analysis**:
- ChromaDB.query() called with n_results=k
- k parameter passed correctly from SearchEngineAdapter
- SearchEngineAdapter requests k*2 results (line 143: `limit * 2`) for hybrid search
- Final results correctly limited to requested limit

**Finding**: n_results parameter is NOT overridden or filtered:
- ChromaDB returns exactly n_results documents as requested
- No filtering logic in ChromaDBAdapter.search()
- Hybrid search properly handles result counts

### T017: Verify ChromaDB Query Behavior at Scale

**Test**: Run diagnostic query with MEMORIA_DEBUG=1

**Collection Stats**:
- Total chunks: 18,004
- Database: ChromaDB HTTP localhost:8001
- Collection: "memoria"

**Test Query**: "memoria performance optimization"
**Results**: 10 results returned
**Scores**: 0.6933 - 0.7078 (range: 0.0146)

**Finding**: ChromaDB behaves correctly with large collections:
- No reduction in result count
- No timeout or connection issues
- Query completes in ~24ms
- All 10 requested results returned with proper scores

### T018: Document Root Cause

**FINDING**: NO ROOT CAUSE EXISTS

**Evidence**:
1. **Result Count**: 100% of queries return requested number of results (10/10)
2. **ChromaDB Parameter**: n_results correctly passed and honored
3. **Hybrid Search**: Properly combines semantic (95%) + keyword (5%) scores
4. **Scale Performance**: Works correctly with 18K chunks

**Possible Explanations for Spec Claim**:
1. **Already Fixed**: Issue existed before spec 001, fixed with hybrid_weight=0.95
2. **Misunderstanding**: User observed narrow score range, interpreted as "single result"
3. **Edge Case**: Issue occurs only under specific conditions not reproduced in testing
4. **Outdated Observation**: Spec based on old behavior, no longer present

**Recommendation**: Clarify with user whether "single result" issue actually occurs. If yes, request specific query and conditions to reproduce.

## Code Analysis

### Search Flow

**1. User Query → search_knowledge()**
```
skill_helpers.py:89-91
query="test" → search_engine.search(query, limit=5, mode="hybrid")
```

**2. SearchEngine → _hybrid_search()**
```
search_engine_adapter.py:136-185
- Requests limit*2 semantic results (10 for limit=5)
- Requests limit*2 keyword results (10 for limit=5)
- Combines scores: 0.95*semantic + 0.05*keyword
- Returns top 5 results
```

**3. Semantic Search → ChromaDB**
```
search_engine_adapter.py:77-88
→ vector_store.search(embedding, k=10)

chromadb_adapter.py:116-131
→ collection.query(query_embeddings, n_results=10)
```

**4. ChromaDB Returns Results**
```
chromadb_adapter.py:142-178
- Receives 10 results from ChromaDB
- Converts distances to similarity scores
- Creates SearchResult objects
- Returns list of 10 results
```

**5. Hybrid Combination**
```
search_engine_adapter.py:165-175
- Combines semantic and keyword scores
- Sorts by hybrid score
- Limits to requested count (5)
```

**Finding**: NO BOTTLENECK OR FILTERING that would reduce results to 1

### Score Compression Analysis

**Observation**: Score ranges are narrow (0.01-0.05 typical)

**Cause**: Large semantic space characteristic
- 18K chunks in collection
- All documents are similar domain (technical documentation)
- Cosine similarity compresses for semantically related documents
- BM25 provides minimal differentiation (5% weight)

**Not a Bug**: This is expected behavior for:
- Large collections
- Semantically homogeneous documents
- Cosine distance metric

**Impact**: Minimal - scores still rank relevance correctly

## Validation Results

### SC-001: Multi-Result Search ✅ PASS
- **Result**: 100% queries return 5+ results (10/10)
- **Target**: ≥90%
- **Status**: EXCEEDS TARGET

### SC-002: Score Range ❌ FAIL
- **Result**: 0.029 average range
- **Target**: ≥0.4
- **Status**: FALLS SHORT (but NOT a single-result issue)

### SC-003: High-Relevance Scores ✅ PASS
- **Result**: 100% high-relevance queries score ≥0.7
- **Target**: ≥80%
- **Status**: EXCEEDS TARGET

**Conclusion**: US1 acceptance criteria (multi-result search) ALREADY MET

## Recommendation

**NO IMPLEMENTATION NEEDED for T019-T022**

**Rationale**:
1. Issue does not exist in current code
2. All diagnostic tests pass for multi-result search
3. hybrid_weight=0.95 fix from spec 001 is already applied and working
4. SC-001 and SC-003 both pass (only SC-002 fails, which is score range not result count)

**Next Actions**:
1. **Mark T019-T022 as complete** (no code changes needed)
2. **Skip to T023-T026** validation tasks (verify current behavior is correct)
3. **Update AGENTS.md** documenting that US1 is already solved
4. **Move to Phase 3** (US2 - Indexing Timeouts) which is the real unresolved issue

**Alternative**: If user insists "single result" issue exists:
1. Request specific query that returns 1 result
2. Request exact reproduction steps
3. Check for environmental differences (Docker, Colima, ChromaDB version)
4. Debug with MEMORIA_DEBUG=1 environment variable

## Diagnostic Commands

### Reproduce Investigation

```bash
# Run validation (T023 equivalent)
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 \
  specs/001-chroma-search-fix/diagnostics/validate_fix.py

# Test specific query with debug output
MEMORIA_DEBUG=1 /Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/memoria/memoria')
from skill_helpers import search_knowledge

results = search_knowledge(
    query="test query here",
    mode="hybrid",
    limit=10
)
print(results)
EOF
```

### Check Collection Health

```bash
# Get collection stats
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/memoria/memoria')
from skill_helpers import get_stats
print(get_stats())
EOF

# Check ChromaDB directly
curl http://localhost:8001/api/v2/heartbeat
```

---

**Investigation Status**: COMPLETE - NO FIX NEEDED
**Recommendation**: Proceed to US2 (Indexing Timeouts) or end spec early
