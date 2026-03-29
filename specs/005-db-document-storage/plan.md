# Implementation Plan: DB-Backed Document Storage & Reindex API

**Branch**: `005-db-document-storage` | **Date**: 2026-03-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-db-document-storage/spec.md`

## Summary

**Primary Requirement**: Eliminate filesystem dependency from memoria. Store full document content in Postgres (relishhost1:5435). ChromaDB remains the vector store (relishhost1:8001). Embeddings via Ollama on relishhost2 using `mxbai-embed-large` (1024-dim vectors) — no local model required.

**Technical Approach**:
1. New `DocumentStorePort` + `PostgresDocumentStoreAdapter` — onion architecture extension
2. New `OllamaEmbeddingAdapter` implementing `EmbeddingGeneratorPort` alongside existing `SentenceTransformerAdapter`; runtime config (`MEMORIA_EMBEDDING_ADAPTER`) selects which is active
3. New domain entities: `StoredDocument`, `ExportManifest`, `ImportResult`, `ReindexResult`
4. New public functions in `skill_helpers.py`: `store_document`, `get_document`, `delete_document`, `list_documents`, `export_corpus`, `import_corpus`, `reindex_corpus`, `migrate_from_docs_folder`
5. Test stubs (in-memory port implementations) for all new ports — integration tests written but `@pytest.mark.integration` skipped until relishhost1/relishhost2 infrastructure is confirmed up

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `psycopg2-binary>=2.9.0` (new), `ollama>=0.4.0` (new), `chromadb>=0.4.0`, `sentence-transformers>=2.2.0` (existing, preserved as alternative adapter)
**Storage**: PostgreSQL on relishhost1:5435 (`memoria` database), ChromaDB on relishhost1:8001
**Embedding**: Ollama on relishhost2:11434, model `mxbai-embed-large` (1024-dim) — default. `SentenceTransformerAdapter` (384-dim, all-MiniLM-L6-v2) available as alternative via `MEMORIA_EMBEDDING_ADAPTER=sentence_transformers`
**Testing**: pytest; unit tests use in-memory stubs (no external services); integration tests `@pytest.mark.integration` committed but skipped until infra is provisioned
**Target Platform**: macOS/Linux (same as existing)
**Project Type**: Python library + STDIO MCP server
**Performance Goals**: export 293 docs <60s, import 293 docs + ~17K chunks <5min, reindex 293 docs <10min
**Constraints**: Backward compatible (all existing `skill_helpers.py` signatures unchanged); no infrastructure runs locally
**Scale/Scope**: 293 documents, ~17K chunks, single-writer access pattern

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Clean Architecture | ✅ PASS | New port in `domain/ports/`, new adapters in `adapters/postgres/` and `adapters/ollama/` — no domain dependencies on adapters |
| II. Immutability | ✅ PASS | All new entities use `@dataclass(frozen=True)` with `__post_init__` validation |
| III. Adapter Pattern | ✅ PASS | `DocumentStorePort` + `OllamaEmbeddingAdapter` both follow existing port/adapter pattern |
| IV. Backward Compatibility | ✅ PASS | All existing `skill_helpers.py` functions unchanged (signatures + behavior) |
| V. Performance | ✅ PASS | Batched import/reindex, streaming export — meets all performance targets |
| VI. Testing Strategy | ⚠️ ADAPTED | Integration tests committed but deferred — see Complexity Tracking |
| **Data Persistence rule** | ⚠️ JUSTIFIED VIOLATION | See Complexity Tracking |
| **Embedding Model rule** | ⚠️ JUSTIFIED VIOLATION | See Complexity Tracking |

## Project Structure

### Documentation (this feature)

```text
specs/005-db-document-storage/
├── plan.md              # This file
├── research.md          # Phase 0 output ✅
├── data-model.md        # Phase 1 output ✅
├── quickstart.md        # Phase 1 output ✅
├── checklists/
│   └── requirements.md  # existing
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
memoria/
├── domain/
│   ├── entities.py                                   # EXTEND: + StoredDocument, ExportManifest, ImportResult, ReindexResult
│   └── ports/
│       ├── document_store.py                         # NEW: DocumentStorePort
│       ├── vector_store.py                           # existing
│       ├── embedding_generator.py                    # existing (OllamaEmbeddingAdapter + SentenceTransformerAdapter both implement this)
│       ├── search_engine.py                          # existing
│       └── document_processor.py                    # existing
├── adapters/
│   ├── postgres/                                     # NEW
│   │   ├── __init__.py
│   │   └── postgres_document_store_adapter.py
│   ├── ollama/                                       # NEW
│   │   ├── __init__.py
│   │   └── ollama_embedding_adapter.py
│   ├── mcp/                                          # IMPLEMENT (was empty)
│   │   ├── __init__.py
│   │   └── server.py
│   ├── stubs/
│   │   ├── document_store_stub.py                   # NEW: in-memory DocumentStorePort
│   │   ├── embedding_stub.py                        # NEW: in-memory EmbeddingGeneratorPort (1024-dim)
│   │   └── vector_store_stub.py                     # NEW: in-memory VectorStorePort
│   ├── chromadb/                                     # existing
│   ├── sentence_transformers/                        # existing (unchanged)
│   ├── search/                                       # existing
│   └── document/                                     # existing
└── skill_helpers.py                                  # EXTEND: + 8 new public functions

tests/
├── unit/
│   ├── test_document_store_port.py                   # NEW: DocumentStoreStub protocol tests
│   ├── test_embedding_port.py                        # NEW: EmbeddingStub protocol tests
│   ├── test_vector_store_port.py                     # NEW: VectorStoreStub protocol tests
│   └── test_skill_helpers.py                         # EXTEND: new functions via stubs
├── integration/
│   ├── test_postgres_document_store_adapter.py       # NEW: @pytest.mark.integration
│   ├── test_ollama_embedding_adapter.py              # NEW: @pytest.mark.integration
│   └── test_document_management.py                  # NEW: end-to-end @pytest.mark.integration
└── conftest.py                                       # EXTEND: skip integration tests unless --run-integration flag
```

**Structure Decision**: Single project (existing layout). All new code slots into existing onion architecture. Stubs in `adapters/stubs/` importable by any test without external services. Integration tests in `tests/integration/` — committed, skipped by default until relishhost1/relishhost2 is provisioned.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Adds Postgres (violates "ChromaDB is single source of truth") | Reindex (FR-006) requires re-reading full document content — ChromaDB chunk metadata cannot reliably reassemble full-text. Export/import (FR-004/005) requires content decoupled from embedding model. Versioning (FR-008) requires structured record store. | Storing full content in ChromaDB metadata hits field size limits (~64KB). SQLite rejected in favour of existing Postgres on relishhost1. |
| Adds `mxbai-embed-large` via Ollama (violates "embedding: all-MiniLM-L6-v2, 384 dims") | All embedding runs on relishhost2 (no local model). mxbai-embed-large (1024 dims) is the deployment target model per clarification. | `SentenceTransformerAdapter` preserved as configurable alternative (FR-015) — not removed. Ollama is the default adapter. Vector dim change requires reindex on model switch (enforced by FR-016). |
| Testing via stubs (adapts "integration tests against real services") | relishhost1/relishhost2 infrastructure not yet provisioned. All business logic is fully testable via in-memory port stubs with zero external services. | Integration tests ARE written and committed — deferred execution only. Will be enabled when user confirms infra is up. |

## Phase 0: Investigation & Root Cause Analysis

*Research complete — see [research.md](research.md)*

**Key decisions resolved**:
- Postgres (relishhost1:5435) over SQLite — uses existing server on relishhost1
- `psycopg2-binary` as sync Postgres driver — matches existing sync skill_helpers.py pattern
- JSON Lines format for export/import — streaming-compatible, human-readable
- `DocumentStorePort` Protocol following existing port pattern
- `OllamaEmbeddingAdapter` using `ollama` Python library — official client, mxbai-embed-large (1024 dims)
- `SentenceTransformerAdapter` preserved — configurable via `MEMORIA_EMBEDDING_ADAPTER`
- Backward compatibility via additive-only public API additions
- Constitution violations formally justified

## Phase 1: Design & Contracts

*Design artifacts complete — see [data-model.md](data-model.md) and [quickstart.md](quickstart.md)*

### New Entities Summary

| Entity | Location | Purpose |
|--------|----------|---------|
| `StoredDocument` | `domain/entities.py` | Full document record with version + fingerprint |
| `ExportManifest` | `domain/entities.py` | Export file header metadata |
| `ImportResult` | `domain/entities.py` | Import operation summary |
| `ReindexResult` | `domain/entities.py` | Reindex operation summary |

### New Ports

**`DocumentStorePort`** in `memoria/domain/ports/document_store.py`:
- `store(source_id, title, content) → StoredDocument` — upsert with version increment on fingerprint change
- `get(source_id) → StoredDocument | None`
- `list_all() → list[StoredDocument]`
- `delete(source_id) → bool`
- `get_fingerprint(source_id) → str | None` — fast change detection
- `export_all() → Iterator[StoredDocument]` — streaming
- `count() → int`
- `health_check() → bool`

### New Adapters

**`PostgresDocumentStoreAdapter`** in `memoria/adapters/postgres/`:
- Manages psycopg2 connection (reads `MEMORIA_PG_*` env vars, defaults to `relishhost1:5435/memoria`)
- `_ensure_schema()` creates `memoria_documents` table + indexes idempotently on first use
- Implements all `DocumentStorePort` methods
- Upsert logic: fingerprint unchanged → no-op; fingerprint changed → update + increment version

**`OllamaEmbeddingAdapter`** in `memoria/adapters/ollama/`:
- Uses `ollama` Python library (`import ollama`)
- Host/port configurable via `MEMORIA_OLLAMA_HOST` (default `relishhost2`), `MEMORIA_OLLAMA_PORT` (default `11434`)
- Default model: `mxbai-embed-large` (1024 dims), configurable via `MEMORIA_OLLAMA_MODEL`
- Implements `EmbeddingGeneratorPort.embed_text(text) → list[float]` and `embed_texts_batch(texts) → list[list[float]]`
- Active when `MEMORIA_EMBEDDING_ADAPTER=ollama` (default)

### Test Stubs

| Stub | Location | Implements |
|------|----------|-----------|
| `DocumentStoreStub` | `adapters/stubs/document_store_stub.py` | `DocumentStorePort` — in-memory dict |
| `EmbeddingStub` | `adapters/stubs/embedding_stub.py` | `EmbeddingGeneratorPort` — returns deterministic vectors (dim=1024) |
| `VectorStoreStub` | `adapters/stubs/vector_store_stub.py` | `VectorStorePort` — in-memory list |

### New Public API Functions (additive, non-breaking)

| Function | Signature | Description |
|----------|-----------|-------------|
| `store_document` | `(content, source_id, title=None) → str` | Store in Postgres + chunk + embed + index in ChromaDB |
| `get_document` | `(source_id) → str` | Return full document content from Postgres |
| `delete_document` | `(source_id) → str` | Remove from Postgres + remove chunks from ChromaDB |
| `list_documents` | `() → list[StoredDocument]` | List all documents from Postgres |
| `export_corpus` | `(output_path) → str` | Stream Postgres → JSONL file with ExportManifest header |
| `import_corpus` | `(input_path) → ImportResult` | Stream JSONL → Postgres + ChromaDB; fingerprint-based upsert |
| `reindex_corpus` | `() → ReindexResult` | Stream Postgres → re-embed → atomically replace ChromaDB collection |
| `migrate_from_docs_folder` | `(docs_dir=None) → ImportResult` | One-time: docs/ folder → Postgres + ChromaDB |

### MCP Server

`memoria/adapters/mcp/server.py` (FastMCP STDIO):
- `search_knowledge(query, mode="hybrid", limit=5)` → chunk results
- `get_document(source_id)` → full document content

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORIA_PG_HOST` | `relishhost1` | Postgres host |
| `MEMORIA_PG_PORT` | `5435` | Postgres port |
| `MEMORIA_PG_DATABASE` | `memoria` | Postgres database name |
| `MEMORIA_PG_USER` | `postgres` | Postgres user |
| `MEMORIA_PG_PASSWORD` | `` | Postgres password |
| `MEMORIA_CHROMA_HOST` | `relishhost1` | ChromaDB host |
| `MEMORIA_CHROMA_PORT` | `8001` | ChromaDB port |
| `MEMORIA_OLLAMA_HOST` | `relishhost2` | Ollama host |
| `MEMORIA_OLLAMA_PORT` | `11434` | Ollama port |
| `MEMORIA_OLLAMA_MODEL` | `mxbai-embed-large` | Embedding model name |
| `MEMORIA_EMBEDDING_ADAPTER` | `ollama` | Active adapter: `ollama` or `sentence_transformers` |

## Phase 2: Implementation

*Tasks generated by `/speckit.tasks` — see [tasks.md](tasks.md)*

**Implementation order** (P1 first, each step independently testable via stubs):

1. **Step 1** (Foundation): New domain entities + `DocumentStorePort`
2. **Step 2** (Adapters): `PostgresDocumentStoreAdapter` + `OllamaEmbeddingAdapter` + all three stubs
3. **Step 3** (Core API): `store_document`, `get_document`, `delete_document`, `list_documents` in skill_helpers
4. **Step 4** (Internals): Update `add_document()` + `index_documents()` to also write to Postgres
5. **Step 5** (Export/Import): `export_corpus`, `import_corpus`
6. **Step 6** (Reindex): `reindex_corpus` (atomic collection swap)
7. **Step 7** (MCP): `memoria/adapters/mcp/server.py`
8. **Step 8** (Migration): `migrate_from_docs_folder`
9. **Step 9** (pyproject.toml): Add `psycopg2-binary`, `ollama` dependencies
10. **Step 10** (Tests): Unit tests using stubs; integration tests written + marked, skipped by default

## Next Steps

1. Run `/speckit.tasks` to regenerate `tasks.md` reflecting `OllamaEmbeddingAdapter`, `VectorStoreStub`, `EmbeddingStub`, deferred integration tests, and updated env vars
2. Run `/speckit.implement` to execute tasks
3. Enable integration tests after infra is up: `pytest tests/integration/ -v --run-integration`
