# ChromaDB Search Diagnostic Data Model

**Feature**: 001-chroma-search-fix
**Purpose**: Define data structures for diagnostic tools and investigation

---

## Diagnostic Entities

### QueryDiagnostic

Represents diagnostic information about a search query.

**Attributes**:
- `query_text: str` - The original query string
- `query_embedding: list[float]` - The generated embedding vector
- `embedding_norm: float` - L2 norm of the query embedding (should be ~1.0 if normalized)
- `embedding_dim: int` - Dimensionality of the embedding (should be 384 for all-MiniLM-L6-v2)
- `timestamp: datetime` - When the query was executed

**Purpose**: Track query characteristics to identify embedding quality issues.

---

### SearchDiagnostic

Represents diagnostic information about search results.

**Attributes**:
- `query: QueryDiagnostic` - The query that produced these results
- `num_results: int` - Number of results returned
- `raw_distances: list[float]` - Raw distance values from ChromaDB
- `similarity_scores: list[float]` - Converted similarity scores (0-1 range)
- `result_ids: list[str]` - Document IDs of returned results
- `execution_time_ms: float` - Total search execution time
- `search_mode: str` - Search mode used (semantic, bm25, hybrid)
- `chromadb_query_time_ms: float` - Time spent in ChromaDB query
- `score_range: float` - max(similarity_scores) - min(similarity_scores)

**Purpose**: Analyze search result quality and identify scoring issues.

**Invariants**:
- `len(raw_distances) == len(similarity_scores) == len(result_ids) == num_results`
- `all(0.0 <= score <= 1.0 for score in similarity_scores)`
- `score_range >= 0.0`

---

### CollectionHealth

Represents health metrics for the ChromaDB collection.

**Attributes**:
- `collection_name: str` - Name of the ChromaDB collection
- `total_documents: int` - Total number of document chunks indexed
- `embedding_dimensions: int` - Dimensionality of stored embeddings
- `distance_metric: str` - Distance metric configured (cosine, euclidean, L2)
- `sample_embedding_norms: list[float]` - L2 norms of sampled embeddings
- `avg_embedding_norm: float` - Average norm across sample
- `std_embedding_norm: float` - Standard deviation of norms
- `vector_space_density: float` - Measure of how tightly clustered embeddings are
- `degenerate_vectors_count: int` - Count of problematic vectors (all zeros, NaN, etc.)
- `index_type: str` - Type of index used (e.g., "HNSW")
- `timestamp: datetime` - When health check was performed

**Purpose**: Diagnose vector space quality and configuration issues.

**Health Indicators**:
- ✅ `avg_embedding_norm ≈ 1.0` (normalized vectors)
- ✅ `std_embedding_norm < 0.1` (consistent normalization)
- ✅ `degenerate_vectors_count == 0` (no corrupt data)
- ⚠️ `vector_space_density > 0.8` may indicate collapsed vector space

---

### TestQueryResult

Represents a single test query with expected vs actual behavior.

**Attributes**:
- `query_text: str` - Test query
- `expected_result_count_min: int` - Minimum expected results
- `expected_result_count_max: int` - Maximum expected results
- `expected_score_min: float` - Minimum expected confidence score for top result
- `actual_result_count: int` - Actual results returned
- `actual_top_score: float` - Actual confidence score of top result
- `actual_score_range: float` - Range of confidence scores
- `passes_criteria: bool` - Whether results meet expectations
- `failure_reason: Optional[str]` - Why test failed (if applicable)

**Purpose**: Track test query validation for success criteria verification.

**Example Usage**:
```python
test = TestQueryResult(
    query_text="claude loop protocol",
    expected_result_count_min=5,
    expected_result_count_max=10,
    expected_score_min=0.7,
    actual_result_count=1,  # CURRENT BROKEN STATE
    actual_top_score=0.52,  # BELOW THRESHOLD
    actual_score_range=0.0,  # NO RANGE (only 1 result)
    passes_criteria=False,
    failure_reason="Only 1 result returned (expected 5-10), score 0.52 < 0.7"
)
```

---

## Diagnostic Data Flows

### Investigation Flow

```
1. Baseline Testing
   QueryDiagnostic (20 test queries)
   → SearchDiagnostic (for each query)
   → TestQueryResult (validation)
   → CSV export for analysis

2. Collection Health Check
   CollectionHealth
   → Sample embeddings analysis
   → Identify vector space issues

3. Root Cause Analysis
   Combine SearchDiagnostic patterns
   + CollectionHealth metrics
   → Identify hypothesis to test
```

### Validation Flow

```
1. Pre-Fix Baseline
   Run test queries → Save SearchDiagnostic baseline

2. Apply Fix
   Modify ChromaDB adapter or search engine

3. Post-Fix Validation
   Run same test queries → Compare SearchDiagnostic
   → Verify success criteria met
```

---

## Diagnostic Tools Data Formats

### Baseline Results CSV

Used by Task 0.1 to export test query results.

**Columns**:
- `query` - Query text
- `num_results` - Results returned
- `top_score` - Highest confidence score
- `score_range` - max - min score
- `raw_distance_min` - Minimum ChromaDB distance
- `raw_distance_max` - Maximum ChromaDB distance
- `search_mode` - Mode used (semantic/hybrid/bm25)
- `execution_time_ms` - Total time

**Example Row**:
```csv
query,num_results,top_score,score_range,raw_distance_min,raw_distance_max,search_mode,execution_time_ms
"claude loop protocol",1,0.52,0.0,0.96,0.96,hybrid,324.5
```

### Collection Stats JSON

Used by Task 0.2 to export collection health data.

**Structure**:
```json
{
  "collection_name": "memoria",
  "total_documents": 1793,
  "embedding_dimensions": 384,
  "distance_metric": "cosine",
  "sample_size": 100,
  "embedding_norms": {
    "mean": 1.0002,
    "std": 0.0234,
    "min": 0.9823,
    "max": 1.0187
  },
  "degenerate_vectors": 0,
  "timestamp": "2026-01-24T10:30:00Z"
}
```

---

## Success Criteria Validation

### Mapping to Data Model

| Success Criterion | Data Model Field | Pass Condition |
|-------------------|------------------|----------------|
| SC-001: 90% queries return 5+ results | `TestQueryResult.actual_result_count` | `>= 5` for 90% of tests |
| SC-002: Score range ≥0.4 | `SearchDiagnostic.score_range` | `>= 0.4` |
| SC-003: High-relevance ≥0.7 | `SearchDiagnostic.similarity_scores[0]` | `>= 0.7` for exact match queries |
| SC-006: Query time <2s | `SearchDiagnostic.execution_time_ms` | `< 2000` |

---

## Implementation Notes

### Python Dataclasses

All diagnostic entities should be implemented as frozen dataclasses for immutability:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class QueryDiagnostic:
    query_text: str
    query_embedding: list[float]
    embedding_norm: float
    embedding_dim: int
    timestamp: datetime
```

### Storage

- Diagnostic results stored in `specs/001-chroma-search-fix/diagnostics/` directory
- CSV for tabular data (baseline results)
- JSON for structured data (collection stats)
- Markdown reports for human-readable analysis

---

## Related Files

- Investigation script: `diagnostics/baseline_test.py` (uses QueryDiagnostic, SearchDiagnostic)
- Validation script: `diagnostics/validate_fix.py` (uses TestQueryResult)
- Health check: `diagnostics/check_collection_health.py` (uses CollectionHealth)
- Interactive debugger: `diagnostics/search_debugger.py` (uses all diagnostic entities)
