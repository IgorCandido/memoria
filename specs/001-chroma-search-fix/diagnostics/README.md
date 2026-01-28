# ChromaDB Search Diagnostics

This directory contains diagnostic scripts and tools for investigating and validating the ChromaDB search quality fix.

## Investigation Scripts (Phase 0)

### baseline_test.py
**Purpose**: Document current broken behavior
**Task**: 0.1 - Current Behavior Baseline
**Usage**: `python baseline_test.py`
**Output**: `baseline_results.csv`

### check_collection_health.py
**Purpose**: Analyze ChromaDB collection and vector space
**Task**: 0.2 - ChromaDB Collection Analysis
**Usage**: `python check_collection_health.py`
**Output**: `collection_stats.json`

### test_distance_formula.py
**Purpose**: Verify distance-to-similarity conversion
**Task**: 0.3 - Distance Metric Audit
**Usage**: `python test_distance_formula.py`
**Output**: Console output with test results

### compare_search_modes.py
**Purpose**: Compare semantic vs keyword vs hybrid search
**Task**: 0.4 - Search Algorithm Analysis
**Usage**: `python compare_search_modes.py`
**Output**: Console output with comparison table

## Validation Scripts (Phase 1)

### validate_fix.py
**Purpose**: Automated validation of all success criteria
**Usage**: `python validate_fix.py`
**Output**: Pass/fail report for SC-001 through SC-007

### search_debugger.py
**Purpose**: Interactive search debugging tool
**Usage**: `python search_debugger.py "query text" [--mode MODE] [--limit N] [--verbose]`
**Output**: Detailed search results with diagnostics

### benchmark_performance.py
**Purpose**: Performance benchmarking before/after fix
**Usage**: `python benchmark_performance.py`
**Output**: Performance metrics (latency, throughput)

## Utility Scripts

### check_embeddings.py
**Purpose**: Verify embedding normalization and quality
**Usage**: `python check_embeddings.py`

### check_chromadb_config.py
**Purpose**: Display ChromaDB configuration
**Usage**: `python check_chromadb_config.py`

### test_known_pairs.py
**Purpose**: Test with known query-document pairs
**Usage**: `python test_known_pairs.py`

### export_baseline.py
**Purpose**: Export search quality metrics to CSV
**Usage**: `python export_baseline.py --output filename.csv`

### compare_baselines.py
**Purpose**: Compare before/after baselines
**Usage**: `python compare_baselines.py before.csv after.csv`

## Data Files

- `baseline_results.csv` - Initial baseline test results (Task 0.1)
- `collection_stats.json` - Collection health data (Task 0.2)
- `before_fix.csv` - Pre-fix baseline (optional)
- `after_fix.csv` - Post-fix validation (optional)

## Development Status

| Script | Status | Priority | Notes |
|--------|--------|----------|-------|
| baseline_test.py | TODO | High | Start with this |
| test_distance_formula.py | TODO | Critical | Most likely root cause |
| check_collection_health.py | TODO | High | Needed for diagnosis |
| compare_search_modes.py | TODO | Medium | For algorithm analysis |
| validate_fix.py | TODO | Critical | Required for validation |
| search_debugger.py | TODO | High | Useful for debugging |
| benchmark_performance.py | TODO | Medium | Performance verification |
| Other utilities | TODO | Low | Nice to have |

## Quick Start

1. **Investigation Phase** (Phase 0):
   ```bash
   # Start with most critical test
   python test_distance_formula.py

   # Then run baseline
   python baseline_test.py

   # Check collection health
   python check_collection_health.py
   ```

2. **After Fix Applied** (Phase 1):
   ```bash
   # Validate all success criteria
   python validate_fix.py

   # Debug specific queries
   python search_debugger.py "test query"
   ```

## Implementation Notes

All scripts should:
- Import from `memoria.skill_helpers` for consistency
- Use diagnostic data models from `../data-model.md`
- Handle ChromaDB connection errors gracefully
- Output results in both human-readable and machine-readable formats
- Be executable standalone (no complex dependencies)

See `../data-model.md` for diagnostic entity definitions.
See `../quickstart.md` for usage instructions.
See `../research.md` for investigation findings.
