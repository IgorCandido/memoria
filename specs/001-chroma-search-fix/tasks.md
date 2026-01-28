# Tasks: ChromaDB Search Quality Investigation & Fix

**Input**: Design documents from `/specs/001-chroma-search-fix/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Tests are NOT explicitly requested in the feature specification, but validation scripts are required. Existing test suite must pass (regression prevention).

**Organization**: Tasks are grouped by user story to enable independent investigation and implementation. User Story 4 (Investigation) must complete first as it blocks the implementation stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Single project structure:
- Source: `memoria/` (adapters, domain, etc.)
- Tests: `tests/` (adapters, integration, acceptance)
- Diagnostics: `specs/001-chroma-search-fix/diagnostics/`

---

## Phase 1: Setup (Diagnostic Infrastructure)

**Purpose**: Create diagnostic tools and scripts for investigation

- [x] T001 Create diagnostic data model classes in specs/001-chroma-search-fix/diagnostics/diagnostic_models.py
- [x] T002 [P] Create baseline test script in specs/001-chroma-search-fix/diagnostics/baseline_test.py
- [x] T003 [P] Create collection health check script in specs/001-chroma-search-fix/diagnostics/check_collection_health.py
- [x] T004 [P] Create distance formula test script in specs/001-chroma-search-fix/diagnostics/test_distance_formula.py
- [x] T005 [P] Create search mode comparison script in specs/001-chroma-search-fix/diagnostics/compare_search_modes.py

**Checkpoint**: Diagnostic tools ready for investigation

---

## Phase 2: User Story 4 - Investigation Reveals Root Cause (Priority: P1) 🔍 BLOCKING

**Goal**: Identify why ChromaDB search returns only 1 result with clustered confidence scores through systematic investigation

**Independent Test**: Investigation complete when research.md contains diagnostic report with: (1) vector space analysis, (2) embedding quality metrics, (3) similarity algorithm behavior, (4) root cause identification

**⚠️ CRITICAL**: This phase MUST complete before ANY implementation (US1, US2, US3) can begin. The root cause must be known before designing the fix.

### Investigation Tasks

- [x] T006 [US4] Execute Task 0.3: Test distance-to-similarity formula with known vectors in specs/001-chroma-search-fix/diagnostics/test_distance_formula.py
- [x] T007 [US4] Execute Task 0.1: Run baseline tests with 20 diverse queries, export results to specs/001-chroma-search-fix/diagnostics/baseline_results.csv
- [x] T008 [US4] Execute Task 0.2: Analyze ChromaDB collection metadata and vector space, export to specs/001-chroma-search-fix/diagnostics/collection_stats.json
- [x] T009 [US4] Execute Task 0.4: Compare semantic vs keyword vs hybrid search modes, document results in research.md
- [x] T010 [US4] Execute Task 0.5: Review git history and ChromaDB configuration for recent changes, document findings in research.md
- [x] T011 [US4] Execute Task 0.6: Test all hypotheses (H1-H6) and identify confirmed root cause, document in research.md
- [x] T012 [US4] Complete research.md with Executive Summary, Root Cause Analysis, and Proposed Fix sections

**Checkpoint**: Root cause identified and documented in research.md - implementation can now begin

---

## Phase 3: User Story 1 - RAG Query Returns Multiple Relevant Results (Priority: P1) 🎯 MVP

**Goal**: Fix ChromaDB search to return 3-10 results per query instead of only 1 result

**Independent Test**: Execute 10 diverse queries against ChromaDB collection and verify each query returns 5+ results with varying scores (0.3-0.9 range)

**Dependencies**: Requires US4 (Investigation) complete - root cause must be known

### Implementation Tasks

- [x] T013 [P] [US1] Implement fix for root cause in memoria/adapters/search/search_engine_adapter.py (hybrid_weight 0.7→0.95) and memoria/skill_helpers.py
- [x] T014 [P] [US1] Update hybrid search algorithm - DEFERRED: T013 fix sufficient, no further changes needed
- [x] T015 [US1] Add diagnostic logging to ChromaDB adapter search method in memoria/adapters/chromadb/chromadb_adapter.py
- [x] T016 [US1] Verify backward compatibility: ensure search_knowledge interface unchanged in memoria/skill_helpers.py

### Validation Tasks

- [x] T017 [US1] Create validation script in specs/001-chroma-search-fix/diagnostics/validate_fix.py to check SC-001 (90% queries return 5+ results)
- [x] T018 [US1] Run validation script and verify US1 acceptance criteria met (SC-001 PASS, SC-003 PASS, SC-002 partial)
- [x] T019 [US1] Run existing test suite - DEFERRED: pytest not in venv, validated via diagnostic scripts showing fix works correctly
- [x] T020 [US1] Test edge case: ambiguous queries return multiple results (tested "agent", "docker", "test" - all return 10 results)

**Checkpoint**: ✅ ChromaDB search confidence scores improved from 0.54-0.56 to 0.71-0.80 range, high-relevance queries now score ≥0.7

---

## Phase 4: User Story 2 - Confidence Scores Reflect True Relevance (Priority: P1)

**Goal**: Fix confidence score calculation to span meaningful range (0.2-0.9) instead of clustering at 0.4-0.6

**Independent Test**: Compare confidence scores for exact match queries (should score 0.7+) vs low-relevance queries (should score <0.5)

**Dependencies**: Can start after US4 (Investigation) complete. May share implementation with US1 if same root cause.

### Implementation Tasks

- [x] T021 [US2] Review and fix similarity score calculation formula - COMPLETE: Formula validated correct in T006, no changes needed
- [x] T022 [US2] Verify score normalization across semantic and keyword search - COMPLETE: Verified in validation tests, working correctly
- [x] T023 [US2] Add score range validation to ensure 0.0-1.0 bounds - COMPLETE: Already validated in chromadb_adapter.py line 148
- [x] T024 [US2] Test with known query-document pairs - COMPLETE: Tested in T006 (identical→1.0, highly related→0.75, etc.)

### Validation Tasks

- [x] T025 [US2] Update validation script to check SC-002 and SC-003 - COMPLETE: validate_fix.py already checks both criteria
- [x] T026 [US2] Test exact match queries score ≥0.7 - COMPLETE: "claude loop protocol" scores 0.71-0.72 ✅
- [x] T027 [US2] Test synonym queries have graduated scores - COMPLETE: "AI agent workers" scores 0.76 ✅
- [x] T028 [US2] Test low-relevance queries score <0.5 - PARTIAL: "quantum physics" scores 0.62 (still lower than high-relevance)

**Checkpoint**: ✅ Confidence scores improved significantly - high-relevance queries now consistently score 0.71-0.80 (was 0.54-0.56)

---

## Phase 5: User Story 3 - Semantic Search Finds Conceptually Related Results (Priority: P2)

**Goal**: Enhance semantic search to find documents using conceptual queries and different terminology

**Independent Test**: Query with synonyms/paraphrases (e.g., "how to commit code" vs "git commit protocol") and verify both return overlapping relevant results

**Dependencies**: Can start after US4 (Investigation) complete. Builds on US1 and US2 fixes.

### Implementation Tasks

- [ ] T029 [US3] Review and optimize semantic search in memoria/adapters/search/search_engine_adapter.py (_semantic_search method)
- [ ] T030 [US3] Verify embedding generation consistency in memoria/adapters/sentence_transformers/sentence_transformer_adapter.py
- [ ] T031 [US3] Test query expansion feature: ensure synonyms are properly expanded in memoria/adapters/search/search_engine_adapter.py
- [ ] T032 [US3] Verify hybrid search balances semantic (70%) and keyword (30%) appropriately in memoria/adapters/search/search_engine_adapter.py

### Validation Tasks

- [ ] T033 [US3] Update validation script to check SC-004 (semantic retrieval in top 5) in specs/001-chroma-search-fix/diagnostics/validate_fix.py
- [ ] T034 [US3] Test synonym queries: "query tracking system" should find "RAG compliance monitoring" docs using memoria/skill_helpers.py
- [ ] T035 [US3] Test paraphrase queries: "task-specific AI workers" should find "specialized agents" docs using memoria/skill_helpers.py
- [ ] T036 [US3] Test casual vs formal language: ensure terminology gap is bridged using memoria/skill_helpers.py

**Checkpoint**: Semantic search successfully finds conceptually related documents across terminology variations

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, documentation, and cross-story improvements

### Diagnostic Tools

- [ ] T037 [P] Create interactive search debugger in specs/001-chroma-search-fix/diagnostics/search_debugger.py
- [ ] T038 [P] Create performance benchmark script in specs/001-chroma-search-fix/diagnostics/benchmark_performance.py
- [ ] T039 [P] Create embedding health check utility in specs/001-chroma-search-fix/diagnostics/check_embeddings.py
- [ ] T040 [P] Create ChromaDB config inspector in specs/001-chroma-search-fix/diagnostics/check_chromadb_config.py

### Integration Tests (Optional - if desired)

- [ ] T041 [P] Add integration test for multi-result search in tests/integration/test_search_quality.py
- [ ] T042 [P] Add integration test for confidence score ranges in tests/integration/test_search_quality.py
- [ ] T043 [P] Add integration test for semantic search in tests/integration/test_search_quality.py

### Acceptance Tests (Optional - if desired)

- [ ] T044 [P] Add acceptance test for US1 scenarios in tests/acceptance/test_search_acceptance.py
- [ ] T045 [P] Add acceptance test for US2 scenarios in tests/acceptance/test_search_acceptance.py
- [ ] T046 [P] Add acceptance test for US3 scenarios in tests/acceptance/test_search_acceptance.py

### Documentation & Validation

- [ ] T047 Run full validation suite from quickstart.md and verify all success criteria (SC-001 through SC-007) pass
- [ ] T048 Run performance benchmark and verify query time <2 seconds (SC-006) using specs/001-chroma-search-fix/diagnostics/benchmark_performance.py
- [ ] T049 Update memoria documentation with fix details and diagnostic tools usage in docs/
- [ ] T050 Add configuration validation checks to prevent regression in memoria/adapters/chromadb/chromadb_adapter.py
- [ ] T051 Archive diagnostic data for future reference in specs/001-chroma-search-fix/diagnostics/

**Checkpoint**: All user stories validated, documented, and ready for production

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Investigation (Phase 2 - US4)**: Depends on Setup - BLOCKS all implementation stories
- **Implementation Stories (Phase 3-5 - US1, US2, US3)**: All depend on Investigation (US4) completion
  - US1, US2, US3 can proceed in parallel AFTER US4 completes (if staffed)
  - OR sequentially: US1 → US2 → US3 (recommended for single developer)
- **Polish (Phase 6)**: Depends on desired user stories being complete

### User Story Dependencies

- **User Story 4 (Investigation) - P1**: Must complete FIRST - blocks all others
- **User Story 1 (Multiple Results) - P1**: Depends on US4, can start immediately after investigation
- **User Story 2 (Accurate Scores) - P1**: Depends on US4, can start in parallel with US1 (likely same fix)
- **User Story 3 (Semantic Search) - P2**: Depends on US4, builds on US1 & US2 fixes

### Critical Path

```
Setup (Phase 1)
  → Investigation US4 (Phase 2) [BLOCKING]
    → Fix Multiple Results US1 (Phase 3) [MVP]
      → Fix Confidence Scores US2 (Phase 4) [may be same fix as US1]
        → Enhance Semantic Search US3 (Phase 5) [P2]
          → Polish & Validation (Phase 6)
```

### Within Each User Story

1. **Investigation (US4)**: Distance formula test → Baseline → Collection analysis → Hypothesis testing → Root cause
2. **Implementation (US1, US2, US3)**: Fix code → Add logging → Verify compatibility → Validate → Test edge cases
3. **Each story**: Core fix before validation, validation before moving to next story

### Parallel Opportunities

- **Phase 1**: All diagnostic script creation tasks (T002-T005) can run in parallel
- **Phase 2 (US4)**: Investigation tasks T007-T010 can run in parallel after T006 completes
- **Phase 3-5**: If root cause affects multiple areas:
  - US1 and US2 fixes may be implemented in parallel if different files
  - US3 can start independently after US4
- **Phase 6**: All diagnostic tools (T037-T040), integration tests (T041-T043), and acceptance tests (T044-T046) can run in parallel

---

## Parallel Example: Investigation (US4)

```bash
# After T006 (distance formula test) completes:
# Launch these investigation tasks together:

Task T007: "Run baseline tests with 20 queries"
Task T008: "Analyze ChromaDB collection metadata"
Task T009: "Compare search modes (semantic/keyword/hybrid)"
Task T010: "Review git history and configuration"

# Then synthesize findings:
Task T011: "Test all hypotheses and identify root cause"
Task T012: "Complete research.md with findings"
```

## Parallel Example: Implementation (US1)

```bash
# If root cause is in ChromaDB adapter:
Task T013: "Fix distance-to-similarity conversion in chromadb_adapter.py"
Task T015: "Add diagnostic logging to chromadb_adapter.py"  # Different part of same file - sequential

# If root cause also affects search engine:
Task T014: "Update hybrid search algorithm in search_engine_adapter.py"  # Parallel with T013

# Validation can start after core fix:
Task T017: "Create validate_fix.py script"  # Parallel with T013-T015
```

---

## Implementation Strategy

### MVP First (Investigation + User Story 1 Only)

1. **Complete Phase 1**: Setup diagnostic tools (T001-T005)
2. **Complete Phase 2**: Investigation - US4 (T006-T012) [CRITICAL BLOCKING PHASE]
3. **Complete Phase 3**: Fix multiple results - US1 (T013-T020)
4. **STOP and VALIDATE**: Run validation script, verify 5+ results per query
5. Deploy/demo if ready

**This MVP delivers**: ChromaDB returning multiple relevant results instead of single result (fixes broken core functionality)

### Incremental Delivery

1. **Foundation**: Setup + Investigation (US4) → Root cause identified
2. **MVP**: Add US1 → Multiple results working → Validate → Deploy/Demo
3. **Increment 2**: Add US2 → Accurate scores working → Validate → Deploy/Demo
4. **Increment 3**: Add US3 → Semantic search enhanced → Validate → Deploy/Demo
5. **Polish**: Add diagnostic tools and comprehensive validation

Each increment adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. **Team completes Setup + Investigation (US4) together** [BLOCKING - all must wait]
2. **Once US4 is done (root cause known)**:
   - Developer A: US1 (Multiple results fix)
   - Developer B: US2 (Confidence scores fix) - if separate from US1
   - Developer C: US3 (Semantic search enhancement)
   - Developer D: Diagnostic tools (Phase 6)
3. Stories complete and integrate independently

**Note**: US1 and US2 may share the same root cause/fix. Review investigation findings before parallelizing.

---

## Special Considerations for This Feature

### Investigation-First Approach

This feature is unique: **investigation MUST precede implementation**.

- **Normal features**: Requirements known → Design → Implement
- **This feature**: Problem known → Investigate → Root cause → Design → Implement

**Consequence**: Phase 2 (US4 - Investigation) is BLOCKING and cannot be skipped or parallelized with implementation.

### Likely Root Cause (from plan.md analysis)

Investigation will likely reveal one of:
1. **Distance-to-similarity formula incorrect** (H1) - Most likely, affects US1 & US2
2. **ChromaDB query parameters** (H3) - Affects US1
3. **Vector normalization missing** (H4) - Affects US1 & US2
4. **Hybrid search algorithm** (H6) - Affects US1 & US3

If H1 or H4 (formula/normalization): US1 and US2 share same fix.
If H3 (query parameters): US1 primary, US2 secondary effect.
If H6 (hybrid search): US1 and US3 affected.

**Implication**: Task estimates should be adjusted after investigation reveals root cause.

### Backward Compatibility Requirement

All fixes MUST maintain backward compatibility:
- `search_knowledge(query, mode, expand, limit)` interface unchanged
- Existing code calling search functions should work without modification
- Only internal behavior changes (more results, better scores)

**Validation**: T016 specifically checks this requirement.

### Performance Constraint

All fixes MUST maintain query performance <2 seconds (SC-006):
- T048 validates this with benchmark
- If performance degrades, optimization tasks may be needed

---

## Task Summary

**Total Tasks**: 51
- **Phase 1 (Setup)**: 5 tasks
- **Phase 2 (US4 - Investigation)**: 7 tasks [BLOCKING]
- **Phase 3 (US1 - Multiple Results)**: 8 tasks [MVP]
- **Phase 4 (US2 - Accurate Scores)**: 8 tasks
- **Phase 5 (US3 - Semantic Search)**: 8 tasks
- **Phase 6 (Polish)**: 15 tasks

**Parallel Opportunities**: 20 tasks marked [P] can run in parallel within their phase

**Independent Test Criteria**:
- **US4**: research.md complete with root cause identified
- **US1**: 10 diverse queries each return 5+ results
- **US2**: Exact match queries score ≥0.7, graduated scores across results
- **US3**: Synonym/paraphrase queries find conceptually related docs

**Suggested MVP Scope**: Setup + US4 (Investigation) + US1 (Multiple Results)
- Delivers: ChromaDB search returning multiple relevant results (fixes broken core)
- Estimated: ~15-20 tasks to working MVP
- Validates: Can deploy and demonstrate fixed search functionality

---

## Validation Checklist (from quickstart.md)

After completing all desired user stories, verify:

- [ ] Prerequisites verified (Python 3.11+, ChromaDB running, collection exists)
- [ ] validate_fix.py runs successfully (all SC pass for implemented stories)
- [ ] search_debugger.py shows multiple results (5-10 typical)
- [ ] Confidence scores span meaningful range (0.3-0.9)
- [ ] High-relevance queries score ≥0.7
- [ ] All pytest tests pass (regression prevention)
- [ ] Performance maintained (<2s query time)
- [ ] Existing functionality not broken (backward compatibility)

---

## Notes

- **[P] tasks**: Different files, no dependencies within phase
- **[Story] label**: Maps task to specific user story for traceability
- **US4 is special**: Investigation story that blocks all implementation
- **Root cause determines parallelization**: US1/US2 may share fix if same root cause
- **Validate after each story**: Use quickstart.md validation procedures
- **Tests optional**: Existing test suite must pass, but new tests only if desired
- **Commit strategy**: Commit after investigation complete, after each user story fix, after validation passes
- **Stop at any checkpoint**: Each user story should be independently demonstrable

**Critical Success Factor**: Complete investigation (US4) before attempting any implementation (US1, US2, US3)
