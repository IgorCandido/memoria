# ChromaDB Search Fix - Validation Quickstart

**Feature**: 001-chroma-search-fix
**Purpose**: Quick guide to validate the ChromaDB search quality fix

---

## Prerequisites

### System Requirements

- **Python**: 3.11+
- **ChromaDB Server**: Running on `localhost:8001` (HTTP mode)
- **Memoria Collection**: Indexed with documents (check with health check below)

### Verify Prerequisites

```bash
# 1. Check Python version
python --version  # Should be 3.11+

# 2. Check ChromaDB is running
curl http://localhost:8001/api/v1/heartbeat
# Expected: {"nanosecond heartbeat":"..."}

# 3. Check memoria collection health
python -c "from memoria.skill_helpers import health_check; print(health_check())"
# Expected: ✅ Connected with document count
```

---

## Quick Validation

### 1. Run Automated Validation Tests

This runs all success criteria checks automatically.

```bash
cd specs/001-chroma-search-fix/diagnostics
python validate_fix.py
```

**Expected Output** (after fix):
```
📊 ChromaDB Search Quality Validation Report
==============================================

Test Suite: 20 diverse queries

Success Criteria Results:
✅ SC-001: 90% of queries return 5+ results
   Status: PASS (95.0% = 19/20 queries)
   Current: 5-10 results per query
   Target: ≥90% with 5+ results

✅ SC-002: Confidence scores span ≥0.4 range
   Status: PASS (average range: 0.52)
   Current: Range 0.30-0.87 typical
   Target: ≥0.4 range

✅ SC-003: High-relevance queries score ≥0.7
   Status: PASS (5/5 exact match queries scored 0.7+)
   Current: Average 0.78 for exact matches
   Target: ≥0.7

✅ SC-004: Semantic queries retrieve in top 5
   Status: PASS (8/10 synonym queries found target)
   Current: 80% retrieval rate
   Target: ≥80%

✅ SC-006: Query time <2 seconds
   Status: PASS (p95: 856ms)
   Current: Average 324ms, p95 856ms
   Target: <2000ms

Overall Status: ✅ ALL SUCCESS CRITERIA MET
```

**If Validation Fails**, see [Troubleshooting](#troubleshooting) section below.

---

### 2. Interactive Search Debugging

Debug individual queries interactively to inspect results.

```bash
cd specs/001-chroma-search-fix/diagnostics
python search_debugger.py "claude loop protocol"
```

**Expected Output** (after fix):
```
🔍 ChromaDB Search Debugger
============================

Query: "claude loop protocol"
Search Mode: hybrid
Query Embedding:
  Dimensions: 384
  Norm: 1.0000 ✓

Searching...

Results: 8 documents found
Execution Time: 324ms

┌────┬───────┬──────────┬─────────────────────────────────┐
│ #  │ Score │ Distance │ Source                          │
├────┼───────┼──────────┼─────────────────────────────────┤
│ 1  │ 0.85  │ 0.30     │ docs/claude-loop-protocol.md    │
│ 2  │ 0.72  │ 0.56     │ docs/agent-catalog.md           │
│ 3  │ 0.68  │ 0.64     │ docs/rag-compliance.md          │
│ 4  │ 0.61  │ 0.78     │ docs/context-engineering.md     │
│ 5  │ 0.54  │ 0.92     │ docs/skills-system.md           │
│ 6  │ 0.48  │ 1.04     │ docs/mcp-tools.md               │
│ 7  │ 0.42  │ 1.16     │ docs/workflow.md                │
│ 8  │ 0.35  │ 1.30     │ docs/quickstart.md              │
└────┴───────┴──────────┴─────────────────────────────────┘

Score Statistics:
  Range: 0.50 (0.85 - 0.35)
  Mean: 0.58
  Std Dev: 0.17

✅ Multiple results with graduated scores (healthy search)
```

**Command Options**:
```bash
# Use different search modes
python search_debugger.py "query text" --mode semantic
python search_debugger.py "query text" --mode bm25
python search_debugger.py "query text" --mode hybrid  # default

# Show more results
python search_debugger.py "query text" --limit 10

# Verbose output (show raw embeddings, more stats)
python search_debugger.py "query text" --verbose
```

---

### 3. Run Full Test Suite

Run pytest to verify all unit, integration, and acceptance tests pass.

```bash
# Run from repository root
cd /Users/igorcandido/Github/thinker/memoria

# Run ChromaDB adapter tests
pytest tests/adapters/chromadb/ -v

# Run search engine adapter tests
pytest tests/adapters/search/ -v

# Run integration tests (requires ChromaDB running)
pytest tests/integration/test_search_quality.py -v

# Run acceptance tests (validates spec.md user stories)
pytest tests/acceptance/test_search_acceptance.py -v

# Run all tests
pytest tests/ -v --tb=short
```

**Expected**: All tests pass ✅

---

## Troubleshooting

### Issue: Still getting single results

**Symptoms**:
- `validate_fix.py` shows SC-001 FAIL (only 1 result per query)
- `search_debugger.py` returns 1 result consistently

**Diagnosis Steps**:

1. **Check ChromaDB is running and accessible**:
   ```bash
   curl http://localhost:8001/api/v1/heartbeat
   ```
   If fails: Start ChromaDB server
   ```bash
   docker start chromadb  # or however your ChromaDB is deployed
   ```

2. **Verify collection exists and has documents**:
   ```bash
   python -c "from memoria.skill_helpers import get_stats; print(get_stats())"
   ```
   Expected: Should show document count (e.g., 1793+ chunks)
   If zero: Re-index documents
   ```bash
   python -c "from memoria.skill_helpers import index_documents; index_documents()"
   ```

3. **Run verbose search debugger**:
   ```bash
   python diagnostics/search_debugger.py "test query" --verbose
   ```
   Check:
   - Is `n_results` parameter being passed correctly to ChromaDB?
   - Are raw distances showing variation (not all the same)?
   - Is query embedding normalized (norm ≈ 1.0)?

4. **Check fix was applied correctly**:
   ```bash
   # Review the fix in ChromaDB adapter
   grep -A 5 "similarity = " memoria/adapters/chromadb/chromadb_adapter.py
   ```
   Should show corrected distance-to-similarity formula

---

### Issue: Scores still clustered 0.4-0.6

**Symptoms**:
- `validate_fix.py` shows SC-002 FAIL (score range < 0.4)
- All results have similar confidence scores

**Diagnosis Steps**:

1. **Check embedding normalization**:
   ```bash
   python diagnostics/check_embeddings.py
   ```
   Expected: All embedding norms should be ≈ 1.0 (normalized)
   If not: Embeddings may need re-normalization

2. **Verify distance metric configuration**:
   ```bash
   python diagnostics/check_chromadb_config.py
   ```
   Expected: Distance metric should be "cosine"
   If different: May need to update similarity formula

3. **Test with known query-document pairs**:
   ```bash
   python diagnostics/test_known_pairs.py
   ```
   This tests queries that should match documents exactly
   Expected: High confidence scores (0.8+) for exact matches

4. **Review distance-to-similarity formula**:
   Check `memoria/adapters/chromadb/chromadb_adapter.py` line ~148
   Formula should correctly convert ChromaDB distance to similarity score

---

### Issue: Tests failing

**Symptoms**:
- `pytest` shows test failures
- Existing functionality broken

**Diagnosis Steps**:

1. **Check which tests are failing**:
   ```bash
   pytest tests/ -v --tb=short | grep FAILED
   ```

2. **Run specific failing test with full output**:
   ```bash
   pytest tests/path/to/test_file.py::test_name -vv
   ```

3. **Verify ChromaDB connection in tests**:
   Some tests may require ChromaDB running. Check if:
   - ChromaDB container is running
   - Test fixtures are set up correctly
   - Test collection is isolated from production

4. **Review test expectations**:
   If tests expected single result behavior (before fix), they may need updates:
   ```bash
   grep -r "assert.*== 1" tests/adapters/chromadb/
   grep -r "assert.*== 1" tests/adapters/search/
   ```
   These assertions may need adjustment to expect multiple results

---

### Issue: Performance degraded

**Symptoms**:
- `validate_fix.py` shows SC-006 FAIL (query time > 2s)
- Searches taking noticeably longer

**Diagnosis Steps**:

1. **Run performance benchmark**:
   ```bash
   python diagnostics/benchmark_performance.py
   ```
   Compare before/after metrics

2. **Profile query execution**:
   ```bash
   python diagnostics/search_debugger.py "test query" --profile
   ```
   Shows time breakdown:
   - Embedding generation time
   - ChromaDB query time
   - Result processing time

3. **Check ChromaDB collection size**:
   ```bash
   python -c "from memoria.skill_helpers import get_stats; print(get_stats())"
   ```
   If significantly larger than expected (>5000 docs), may need optimization

4. **Verify ChromaDB index**:
   Large collections may benefit from HNSW index tuning
   See ChromaDB documentation for index optimization

---

## Validation Checklist

Use this checklist to verify the fix is complete:

- [ ] Prerequisites verified (Python 3.11+, ChromaDB running, collection exists)
- [ ] `validate_fix.py` runs successfully (all SC pass)
- [ ] `search_debugger.py` shows multiple results (5-10 typical)
- [ ] Confidence scores span meaningful range (0.3-0.9)
- [ ] High-relevance queries score ≥0.7
- [ ] All pytest tests pass
- [ ] Performance maintained (<2s query time)
- [ ] Existing functionality not broken (backward compatibility)

---

## Additional Diagnostic Tools

### Check Collection Health

```bash
python diagnostics/check_collection_health.py
```

Shows:
- Total documents indexed
- Embedding dimensions
- Distance metric configured
- Sample embedding statistics
- Vector space health indicators

### Export Baseline for Comparison

Before applying fix:
```bash
python diagnostics/export_baseline.py --output before_fix.csv
```

After applying fix:
```bash
python diagnostics/export_baseline.py --output after_fix.csv
python diagnostics/compare_baselines.py before_fix.csv after_fix.csv
```

Shows side-by-side comparison of search quality metrics.

---

## Getting Help

If validation fails after following troubleshooting steps:

1. **Review investigation findings**: Check `research.md` for root cause details
2. **Check diagnostic data**: Review files in `diagnostics/` directory
3. **Examine logs**: Look for errors in ChromaDB server logs
4. **Consult plan**: Review `plan.md` for implementation details

---

## Next Steps After Validation

Once all validation checks pass:

1. **Document results**: Update `research.md` with validation confirmation
2. **Commit changes**: Create git commit with fix and validation results
3. **Update documentation**: Add learnings to memoria docs
4. **Archive diagnostics**: Keep diagnostic data for future reference
5. **Monitor production**: Track search quality metrics over time

---

**Last Updated**: 2026-01-24
**Status**: Template - To be updated after fix implementation
