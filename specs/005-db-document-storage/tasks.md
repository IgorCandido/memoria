# Tasks: DB-Backed Document Storage & Reindex API

**Feature**: 005-db-document-storage
**Input**: Design documents from `specs/005-db-document-storage/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, quickstart.md ✅

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Parallelizable — different files, no in-flight dependencies
- **[USn]**: User story label (US1–US6, from spec.md priorities)
- No [P] when multiple tasks touch the same file

---

## Phase 1: Setup

**Purpose**: Add new dependencies, create package structure, configure test infrastructure

- [X] T001 Add `psycopg2-binary>=2.9.0` and `ollama>=0.4.0` to `[project.dependencies]` in `pyproject.toml`
- [X] T002 [P] Create empty `__init__.py` for new adapter packages: `memoria/adapters/postgres/__init__.py`, `memoria/adapters/ollama/__init__.py`, `memoria/adapters/mcp/__init__.py`; verify `memoria/adapters/stubs/__init__.py` exists
- [X] T003 [P] Create `tests/unit/__init__.py` and `tests/integration/__init__.py` (empty files to make them packages)
- [X] T004 [P] Create or update `tests/conftest.py` to add `--run-integration` pytest flag: register custom mark `integration` and skip all `@pytest.mark.integration` tests unless `--run-integration` CLI flag is passed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Domain entities, ports, all adapters, all stubs, and the factory wiring in skill_helpers — must be complete before any user story can begin

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Extend `memoria/domain/entities.py` with four new frozen dataclasses: `StoredDocument` (source_id, title, content, fingerprint, version, created_at, updated_at, id=""), `ExportManifest` (exported_at, document_count, system_version, format_version), `ImportResult` (documents_added, documents_updated, documents_skipped, documents_failed, errors: tuple[tuple[str,str],...], duration_seconds), `ReindexResult` (documents_processed, chunks_created, documents_failed, errors, duration_seconds, embedding_model); each with `__post_init__` validation of invariants
- [X] T006 Create `memoria/domain/ports/document_store.py` with `DocumentStorePort(Protocol)` defining: `store(source_id, title, content) -> StoredDocument`, `get(source_id) -> StoredDocument | None`, `list_all() -> list[StoredDocument]`, `delete(source_id) -> bool`, `get_fingerprint(source_id) -> str | None`, `export_all() -> Iterator[StoredDocument]`, `count() -> int`, `health_check() -> bool`
- [X] T007 Create `memoria/adapters/postgres/postgres_document_store_adapter.py` implementing all `DocumentStorePort` methods: reads `MEMORIA_PG_*` env vars (defaults: host=relishhost1, port=5435, database=memoria, user=postgres); `_ensure_schema()` creates `memoria_documents` table + indexes idempotently (DDL from data-model.md); `store()` computes SHA-256 fingerprint and upserts (no-op if fingerprint unchanged, else update + increment version); `export_all()` yields `StoredDocument` rows as a streaming generator
- [X] T008 [P] Create `memoria/adapters/ollama/ollama_embedding_adapter.py` implementing `EmbeddingGeneratorPort`: uses `import ollama`; reads `MEMORIA_OLLAMA_HOST` (default `relishhost2`), `MEMORIA_OLLAMA_PORT` (default `11434`), `MEMORIA_OLLAMA_MODEL` (default `mxbai-embed-large`); implements `embed_text(text: str) -> list[float]` via `ollama.Client(host=...).embeddings(model=..., prompt=text)`; implements `embed_texts_batch(texts) -> list[list[float]]` as sequential calls; active when `MEMORIA_EMBEDDING_ADAPTER=ollama`
- [X] T009 [P] Create `memoria/adapters/stubs/document_store_stub.py` with `DocumentStoreStub` implementing `DocumentStorePort` using an in-memory dict — no external dependencies; `store()` computes SHA-256 fingerprint, upserts in dict; `export_all()` yields stored documents; all methods mirror the production adapter contract
- [X] T010 [P] Create `memoria/adapters/stubs/embedding_stub.py` with `EmbeddingStub` implementing `EmbeddingGeneratorPort`: returns deterministic zero vectors of configurable dimension (default `dim=1024` to match `mxbai-embed-large`); constructor accepts `dim: int = 1024`
- [X] T011 [P] Create `memoria/adapters/stubs/vector_store_stub.py` with `VectorStoreStub` implementing `VectorStorePort`: in-memory list storage; `add_documents()` appends; `search()` returns first N stored chunks with score=1.0; `delete_by_source()` filters by source_id; matches the contract of `ChromaDBAdapter`
- [X] T012 Add `_get_document_store() -> DocumentStorePort` and `_get_embedding_adapter() -> EmbeddingGeneratorPort` factory functions to `memoria/skill_helpers.py`: `_get_document_store()` reads `MEMORIA_PG_*` env vars and returns `PostgresDocumentStoreAdapter`; `_get_embedding_adapter()` reads `MEMORIA_EMBEDDING_ADAPTER` env var — returns `OllamaEmbeddingAdapter` if `ollama` (default), `SentenceTransformerAdapter` if `sentence_transformers`

**Checkpoint**: Foundation ready — all ports, adapters, stubs, and factories in place. User story implementation can now begin.

---

## Phase 3: User Story 1 - Store Documents in Database (Priority: P1) MVP

**Goal**: Store full document content in Postgres via API, without requiring any `/docs` folder. Document is chunked, embedded (via active embedding adapter), and searchable via `search_knowledge()`.

**Independent Test**: Set `MEMORIA_EMBEDDING_ADAPTER=ollama`, call `store_document(content="# Test\nContent", source_id="test/doc")` with no `/docs` folder present. Verify row exists in `memoria_documents`, `get_document("test/doc")` returns the content, and `search_knowledge("Test")` returns chunks from it.

- [X] T013 [US1] Add `store_document(content: str, source_id: str, title: str = None) -> str` to `memoria/skill_helpers.py`: (1) `_get_document_store().store(source_id, title or source_id, content)`, (2) delete existing ChromaDB chunks for source_id, (3) chunk content using existing `DocumentProcessorAdapter`, (4) embed chunks using `_get_embedding_adapter()`, (5) add chunks to ChromaDB via existing `ChromaDBAdapter`, (6) return summary string with source_id and chunk count
- [X] T014 [US1] Add `get_document(source_id: str) -> str` to `memoria/skill_helpers.py`: call `_get_document_store().get(source_id)`, return `StoredDocument.content`; raise `ValueError` with clear "not found: {source_id}" message if missing
- [X] T015 [US1] Update `add_document(file_path, reindex)` in `memoria/skill_helpers.py` to also call `_get_document_store().store(source_id=file_path, title=os.path.basename(file_path), content=file_text)` after reading the file and before chunking — existing function signature and return value unchanged
- [X] T016 [US1] Update `index_documents(pattern, rebuild)` in `memoria/skill_helpers.py` to call `_get_document_store().store(...)` for each document it reads from disk — existing function signature and return value unchanged

**Checkpoint**: US1 complete — documents stored in Postgres, searchable without `/docs` folder.

---

## Phase 4: User Story 2 - Export Full Corpus to File (Priority: P1)

**Goal**: Export all documents from Postgres to a JSONL file: `ExportManifest` JSON on line 1, one `StoredDocument` JSON per subsequent line. Streaming — never loads full corpus into memory.

**Independent Test**: Store 3 documents, call `export_corpus("/tmp/test-export.jsonl")`, open file, verify line 1 parses as `ExportManifest` JSON with correct `document_count=3`, and remaining lines each parse as valid document JSON with `content` field present.

- [X] T017 [US2] Add `export_corpus(output_path: str) -> str` to `memoria/skill_helpers.py`: open file for write; write `ExportManifest` (exported_at=now, document_count=`count()`, system_version from VERSION file, format_version="1.0") as first line JSON; then stream `_get_document_store().export_all()` writing each `StoredDocument` as one JSON line; use `ProgressTracker` pattern; return summary string with doc count and path

**Checkpoint**: US2 complete — full corpus export to JSONL works.

---

## Phase 5: User Story 3 - Import and Batch Re-import from File (Priority: P1)

**Goal**: Import documents from a JSONL export file into Postgres and ChromaDB in batches. Idempotent via fingerprint — unchanged documents are skipped. Streaming — never loads full corpus into memory.

**Independent Test**: Use export file from US2 test. Call `import_corpus("/tmp/test-export.jsonl")` on a clean system. Verify `ImportResult.documents_added == 3`, all documents searchable. Re-run — verify `ImportResult.documents_skipped == 3`. Pass a corrupted file — verify `ValueError` raised and no partial state left.

- [X] T018 [US3] Add `import_corpus(input_path: str) -> ImportResult` to `memoria/skill_helpers.py`: open JSONL file; read line 1 as manifest (validate format_version); stream remaining lines; for each document call `_get_document_store().get_fingerprint()` to detect unchanged docs (skip if match); call `_get_document_store().store()` then chunk + embed via `_get_embedding_adapter()` + index into ChromaDB in batches of 10 docs; use `ProgressTracker`; collect per-doc errors; on corrupted file raise `ValueError` with context and no partial writes; return `ImportResult`

**Checkpoint**: US3 complete — export/import round-trip works.

---

## Phase 6: User Story 4 - Reindex All Documents (Priority: P2)

**Goal**: Re-read all documents from Postgres, create a fresh ChromaDB collection with new embeddings, then atomically swap it as the active collection. Old collection remains intact if reindex fails mid-way.

**Independent Test**: Store documents, call `reindex_corpus()`, verify `ReindexResult.documents_processed` equals stored count, all chunks re-created, `search_knowledge()` returns results. Interrupt during reindex (mock failure) — verify old collection still responds.

- [X] T019 [US4] Add `reindex_corpus() -> ReindexResult` to `memoria/skill_helpers.py`: stream all documents from `_get_document_store().export_all()`; write all chunks to a temporary ChromaDB collection (named `memoria_reindex_{timestamp}`); on complete success swap the temp collection as the active `memoria` collection and delete the old one; on any failure leave the old collection intact and delete the temp collection; use `ProgressTracker`; collect per-doc errors; return `ReindexResult` with `embedding_model` = active model name from `_get_embedding_adapter()`

**Checkpoint**: US4 complete — atomic reindex leaves system consistent on failure.

---

## Phase 7: User Story 5 - Document Lifecycle Management (Priority: P2)

**Goal**: Delete and list documents through the API — no filesystem access required.

**Independent Test**: Store 3 documents. `list_documents()` returns all 3 with correct metadata. `delete_document("test/doc")` returns success, document absent from subsequent `list_documents()`, and its chunks absent from `search_knowledge()`. `delete_document("nonexistent")` returns clear "not found" string.

- [X] T020 [US5] Add `delete_document(source_id: str) -> str` to `memoria/skill_helpers.py`: call `_get_document_store().delete(source_id)`; if `False` (not found) return "not found: {source_id}"; otherwise delete all ChromaDB chunks for source_id via existing adapter; return summary string confirming deletion
- [X] T021 [US5] Add `list_documents() -> list[StoredDocument]` to `memoria/skill_helpers.py`: call `_get_document_store().list_all()` and return the result; `list_all()` returns documents without content field (metadata only) per the port contract — full content retrievable via `get_document()`

**Checkpoint**: US5 complete — full document lifecycle management via API.

---

## Phase 8: User Story 6 - Legacy Migration from /docs Folder (Priority: P3)

**Goal**: One-time bulk import of all `.md` and `.txt` files from a `/docs` folder into Postgres + ChromaDB. Idempotent — already-current documents are skipped based on fingerprint.

**Independent Test**: Point `migrate_from_docs_folder` at the existing `memoria/docs/` directory. Run migration, verify `ImportResult.documents_added` equals file count, all searchable. Remove docs dir, verify `search_knowledge()` still works. Run again — verify `ImportResult.documents_skipped` equals file count.

- [X] T022 [US6] Add `migrate_from_docs_folder(docs_dir: str = None) -> ImportResult` to `memoria/skill_helpers.py`: default `docs_dir` to `os.path.join(os.path.dirname(__file__), "docs")`; walk directory recursively for `.md` and `.txt` files; for each file compute SHA-256 fingerprint of content, check `_get_document_store().get_fingerprint(source_id)` to skip unchanged files; call `store_document()` for new/changed files; use `ProgressTracker`; collect per-file errors; return `ImportResult`

**Checkpoint**: US6 complete — one-time legacy migration works idempotently.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: MCP server, unit tests using stubs (immediate), integration tests (committed but deferred)

- [X] T023 [P] Implement `memoria/adapters/mcp/server.py` as a FastMCP STDIO server: expose `search_knowledge(query: str, mode: str = "hybrid", limit: int = 5) -> str` wrapping the existing skill_helpers function; expose `get_document(source_id: str) -> str` wrapping the new skill_helpers function; update `memoria/adapters/mcp/__init__.py`
- [X] T024 [P] Create `tests/unit/test_document_store_port.py`: test `DocumentStoreStub` covers all `DocumentStorePort` methods — `store()` insert + upsert + fingerprint no-op, `get()` found + not found, `delete()` present + absent, `get_fingerprint()`, `export_all()` yields all, `count()`, `list_all()`; no external services
- [X] T025 [P] Create `tests/unit/test_embedding_port.py`: test `EmbeddingStub` — `embed_text()` returns list of length 1024, `embed_texts_batch()` returns correct count and dimensions; verify `OllamaEmbeddingAdapter` and `SentenceTransformerAdapter` structurally satisfy `EmbeddingGeneratorPort` protocol
- [X] T026 [P] Create `tests/unit/test_vector_store_port.py`: test `VectorStoreStub` — `add_documents()` stores docs, `search()` returns results, `delete_by_source()` removes correct entries; verify structural conformance to `VectorStorePort`
- [X] T027 Extend `tests/unit/test_skill_helpers.py` with unit tests for all 8 new public functions using injected stubs (patch `_get_document_store` and `_get_embedding_adapter` returns): `store_document`, `get_document`, `delete_document`, `list_documents`, `export_corpus`, `import_corpus`, `reindex_corpus`, `migrate_from_docs_folder`; verify backward compatibility of existing functions remains unchanged
- [X] T028 [P] Create `tests/integration/test_postgres_document_store_adapter.py` marked `@pytest.mark.integration`: test `PostgresDocumentStoreAdapter` against real Postgres on relishhost1 — `_ensure_schema()` idempotency, `store()` insert + upsert + no-op, `get()`, `delete()`, `export_all()` streaming, `count()`, `health_check()`; decorated `@pytest.mark.integration` so skipped by default
- [X] T029 [P] Create `tests/integration/test_ollama_embedding_adapter.py` marked `@pytest.mark.integration`: test `OllamaEmbeddingAdapter` against real Ollama on relishhost2 — `embed_text()` returns 1024-element float list, `embed_texts_batch()` returns correct count; decorated `@pytest.mark.integration`
- [X] T030 [P] Create `tests/integration/test_document_management.py` marked `@pytest.mark.integration`: end-to-end acceptance tests against real infrastructure — US1 (store → get → search without /docs), US2+US3 (export → import → verify), US4 (reindex → search), US5 (store → list → delete → verify absent), US6 (migrate → remove dir → verify search); decorated `@pytest.mark.integration`
- [X] T031 Run quickstart.md validation sequence end-to-end (requires infrastructure up): verify infrastructure, run schema setup, `store_document` → `get_document` → `search_knowledge`, `export_corpus` → `import_corpus`, `reindex_corpus`; fix any issues found

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately; T002, T003, T004 parallel with T001
- **Phase 2 (Foundational)**: After Phase 1. T005 first → T006 → T007; T008 [P] with T007 (different files, after T006); T009 [P] with T007 (different files, after T006); T010 [P] and T011 [P] are independent (existing ports, can start any time). T012 after T007+T008. **BLOCKS all user stories.**
- **Phase 3 (US1)**: After Phase 2 — T013 → T014 → T015 → T016 (sequential, all in skill_helpers.py)
- **Phase 4 (US2)**: After Phase 2 — T017 (skill_helpers.py, after US1 tasks)
- **Phase 5 (US3)**: After Phase 2 — T018 (skill_helpers.py, after US2 tasks)
- **Phase 6 (US4)**: After Phase 2 — T019 (skill_helpers.py, after US3 tasks)
- **Phase 7 (US5)**: After Phase 2 — T020 → T021 (skill_helpers.py, after US4 tasks)
- **Phase 8 (US6)**: After Phase 2 — T022 (skill_helpers.py, after US5 tasks)
- **Phase 9 (Polish)**: After all user story phases; T023–T030 [P] in parallel; T031 after all, requires infrastructure

### User Story Dependencies

- **US1 (P1)**: After Phase 2 only — stores to Postgres + ChromaDB via active embedding adapter
- **US2 (P1)**: After Phase 2; logically needs US1 complete (documents to export)
- **US3 (P1)**: After Phase 2; needs US2 export format defined
- **US4 (P2)**: After Phase 2; needs US1 (documents to reindex)
- **US5 (P2)**: After Phase 2; compatible with US1
- **US6 (P3)**: After Phase 2; independent, can be last

### Parallel Opportunities

```bash
# Phase 1 — parallel after T001
Task: "Create adapter package __init__.py files"           # T002
Task: "Create tests/unit/ and tests/integration/ dirs"    # T003
Task: "Update tests/conftest.py with integration flag"    # T004

# Phase 2 — parallel after T006 completes
Task: "Create PostgresDocumentStoreAdapter"               # T007
Task: "Create OllamaEmbeddingAdapter"                     # T008 [P]
Task: "Create DocumentStoreStub"                          # T009 [P]
Task: "Create EmbeddingStub"                              # T010 [P]
Task: "Create VectorStoreStub"                            # T011 [P]

# Phase 9 — all parallel
Task: "Implement MCP server"                              # T023
Task: "Unit tests: document_store_port"                   # T024
Task: "Unit tests: embedding_port"                        # T025
Task: "Unit tests: vector_store_port"                     # T026
Task: "Integration test: postgres adapter (deferred)"     # T028
Task: "Integration test: ollama adapter (deferred)"       # T029
Task: "Integration test: end-to-end (deferred)"          # T030
```

---

## Implementation Strategy

### MVP Scope (US1 only — Phases 1–3)

1. Complete Phase 1: Setup (T001–T004)
2. Complete Phase 2: Foundational (T005–T012)
3. Complete Phase 3: User Story 1 (T013–T016)
4. **STOP and VALIDATE**: `store_document(content="# Test", source_id="test")` stores in Postgres, `get_document("test")` returns content, `search_knowledge("Test")` returns chunks — all with no `/docs` folder
5. Proceed to US2 (export) once US1 validated

### Incremental Delivery

1. Setup + Foundational → all ports, adapters, stubs wired
2. US1 (Store) → MVP: filesystem-free ingestion with Ollama embeddings
3. US2 (Export) → safe backup capability
4. US3 (Import) → full backup/restore cycle
5. US4 (Reindex) → enables spec 004 (configurable embeddings)
6. US5 (Lifecycle) → full CRUD API
7. US6 (Migration) → legacy adoption path
8. Polish → unit tests run immediately; integration tests enabled when relishhost1/relishhost2 infra is up

### Integration Test Activation

When infrastructure is provisioned (localLab spec 019-memoria-infrastructure deployed):

```bash
# Verify infrastructure first
psql -h relishhost1 -p 5435 -U postgres -c "\l" | grep memoria
curl http://relishhost1:8001/api/v1/heartbeat
curl http://relishhost2:11434/api/embeddings -d '{"model":"mxbai-embed-large","prompt":"test"}'

# Then run integration tests
pytest tests/integration/ -v --run-integration
```

---

## Summary

| Phase | Tasks | Story | Priority |
|-------|-------|-------|----------|
| Setup | T001–T004 | — | — |
| Foundational | T005–T012 | — | Blocks all |
| US1: Store Documents | T013–T016 | US1 | P1 / MVP |
| US2: Export Corpus | T017 | US2 | P1 |
| US3: Import Corpus | T018 | US3 | P1 |
| US4: Reindex | T019 | US4 | P2 |
| US5: Lifecycle | T020–T021 | US5 | P2 |
| US6: Migration | T022 | US6 | P3 |
| Polish | T023–T031 | — | — |
| **Total** | **31** | | |

**Parallel [P] tasks**: 14 across setup, foundational, and polish phases.
**MVP**: Complete Phases 1–3 (T001–T016) for a fully functional filesystem-free document store with Ollama embeddings.
**Integration tests**: Written in T028–T030, deferred execution until `--run-integration` flag used after infra confirmed up.
