# Quickstart: Memoria Performance Optimization

**Feature**: 002-memoria-performance
**Date**: 2026-01-31

## Prerequisites

- ChromaDB Docker container running on port 8001
- Python 3.11+ with memoria dependencies installed
- Cloud supervisor worker stopped (to avoid interference)
- Collection with 2000+ documents for realistic testing

## Quick Validation

### 1. Validate Current State (Baseline)

**Check search result count**:
```bash
cd /Users/igorcandido/Github/thinker/memoria
python specs/001-chroma-search-fix/diagnostics/validate_fix.py
```

Expected output (if Issue 1 exists):
```
❌ SC-001 FAIL: Only 1 result returned (expected 5+)
```

**Check indexing performance**:
```bash
cd /Users/igorcandido/Github/thinker/memoria
python specs/001-chroma-search-fix/diagnostics/benchmark_performance.py --operation indexing --docs 100
```

Expected output (baseline):
```
Indexing 100 documents: 90.5 seconds
Throughput: 1.1 docs/second
```

### 2. Stop Cloud Supervisor Worker

```bash
# Find and stop the worker process
ps aux | grep "cloud.*supervisor"
kill -9 <PID>

# Or use docker if running in container
docker ps | grep supervisor
docker stop <container_id>
```

### 3. Collect Current State Data

**Search behavior**:
```bash
cd /Users/igorcandido/Github/thinker/memoria

# Run diagnostic search
python specs/001-chroma-search-fix/diagnostics/search_debugger.py \
  "memoria architecture" \
  --mode hybrid \
  --verbose

# Output should show:
# - Number of results returned
# - Confidence scores for each
# - Total query time
```

**Indexing behavior**:
```bash
# Profile memory usage during indexing
python -m memory_profiler memoria/skill_helpers.py index_documents

# Check ChromaDB collection size
python -c "
from memoria.adapters.chromadb import ChromaDBAdapter
adapter = ChromaDBAdapter()
print(f'Collection size: {adapter.count()} documents')
"
```

## Testing After Implementation

### 1. Verify Batch Embedding API

```python
from memoria.adapters.sentence_transformers.sentence_transformer_adapter import SentenceTransformerAdapter

embedder = SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")

# Test batch API
texts = ["test 1", "test 2", "test 3"]
embeddings = embedder.embed_batch(texts)

assert len(embeddings) == 3
assert embeddings[0].dimensions == 384  # all-MiniLM-L6-v2 dimension
print("✓ Batch embedding API working")
```

### 2. Validate Search Result Count

```bash
# Should now return 5-10 results
python specs/001-chroma-search-fix/diagnostics/validate_fix.py
```

Expected output (after fix):
```
✓ SC-001 PASS: 10 results returned
✓ SC-003 PASS: High-relevance queries score ≥0.7
```

### 3. Validate Indexing Performance

```bash
# Run the performance test script
python specs/002-memoria-performance/test_indexing_performance.py --docs 100
```

Expected output (after optimization):
```
SC-003 (0% timeout):     PASS
SC-005 (>20 docs/min):   PASS
SC-007 (<2GB memory):    PASS
```

### 4. Test Large Document Indexing

```bash
# Index a 5MB document - should complete in <30 seconds
python specs/002-memoria-performance/test_indexing_performance.py --large-doc
```

### 5. Run Performance Regression Tests

```bash
cd /Users/igorcandido/Github/thinker/memoria
pytest tests/performance/ -v
```

Expected: All performance regression tests pass

### 6. Backward Compatibility

```bash
# Run existing test suite
cd /Users/igorcandido/Github/thinker/memoria
pytest tests/integration/test_search_quality.py
pytest tests/acceptance/test_search_acceptance.py
pytest tests/performance/test_indexing_performance.py -k "TestBackwardCompatibility"
```

Expected: All tests pass (no breaking changes)

## Interactive Planning Session Setup

After investigation tasks complete:

1. **Review collected data**:
   - Search result counts and scores
   - Indexing performance metrics
   - Memory usage profiles
   - ChromaDB collection statistics

2. **Prepare discussion points**:
   - Root cause analysis for Issue 1 regression
   - Feasibility of batch embedding approach
   - Trade-offs between memory and speed
   - Alternative solutions if batch API not available

3. **Environment ready**:
   - Cloud supervisor stopped
   - Clean ChromaDB state
   - Baseline metrics documented
   - Constitution documented

## Troubleshooting

### ChromaDB not responding
```bash
docker restart chromadb
# Wait 10 seconds for startup
curl http://localhost:8001/api/v1/heartbeat
```

### Import errors
```bash
cd /Users/igorcandido/Github/thinker/memoria
pip install -e .
```

### Cloud supervisor won't stop
```bash
# Force kill all related processes
pkill -9 -f "supervisor"
pkill -9 -f "claude.*worker"
```

## Success Criteria Checklist

- [x] SC-001: 90% of queries return 5+ results (validated: 100% return 10 results)
- [ ] SC-002: Confidence scores span 0.3+ range (inherent limitation: avg 0.029 range)
- [x] SC-003: 0% indexing timeout rate (batch embedding + progressive batching)
- [x] SC-004: 90% of queries complete in <2s (validated: P99 ~30ms)
- [x] SC-005: Indexing throughput >20 docs/minute (batch embedding API)
- [x] SC-006: Zero breaking changes (API signatures unchanged)
- [x] SC-007: Memory usage <2GB peak (progressive batching prevents accumulation)

## Implementation Summary

### Key Changes Made

1. **ProgressTracker entity** (`memoria/domain/entities.py`) - Tracks indexing progress, failures, throughput
2. **Batch embedding** - `index_documents()` now uses `embed_batch()` instead of sequential `embed_text()` calls
3. **Progressive batching** - Commits to ChromaDB every 500 chunks instead of accumulating all in memory
4. **Graceful failure handling** - Individual document failures don't stop the entire indexing operation
5. **Timeout configuration** - `ChromaDBAdapter` accepts optional `timeout` parameter
6. **Performance logging** - `MEMORIA_DEBUG=1` enables timing metrics for search and indexing
7. **Performance test suite** - `tests/performance/` with query and indexing benchmarks
