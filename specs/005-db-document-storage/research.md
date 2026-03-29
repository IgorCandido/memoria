# Research: DB-Backed Document Storage & Reindex API

**Feature**: 005-db-document-storage
**Phase**: 0 - Research
**Date**: 2026-03-07

---

## Decision 1: Postgres vs SQLite for Document Store

**Decision**: PostgreSQL on relishhost1 (port 5435, shared Docker instance, `memoria` database)

**Rationale**:
- Postgres on relishhost1:5435 is provisioned via localLab spec 019-memoria-infrastructure — zero new server required
- Postgres provides ACID guarantees, concurrent access, and large TEXT columns (unlimited content size)
- Consistent with project infrastructure patterns (relishhost1 is the primary services host)
- Enables future multi-host scenarios (SQLite is single-file/single-process)

**Alternatives considered**:
- **SQLite**: Portable, zero setup, but single-writer, not suited for concurrent multi-agent access. Also creates a new file artifact that must be managed alongside ChromaDB.
- **Store content in ChromaDB metadata**: ChromaDB metadata fields have practical limits (~64KB per field). Full documents can exceed this. Also, metadata retrieval by source requires `get()` with a where-filter, which is less efficient than a dedicated indexed table.

---

## Decision 2: Postgres Client Library

**Decision**: `psycopg2-binary>=2.9.0`

**Rationale**:
- All existing skill_helpers.py code is synchronous — no async needed
- `psycopg2-binary` is a self-contained wheel with no C compilation requirement
- Mature library, stable API, well-understood connection pool patterns
- `psycopg3` (psycopg) is newer but less widespread in existing infrastructure

**Alternatives considered**:
- `asyncpg`: Async only — incompatible with sync skill_helpers.py
- `psycopg3`: Newer, better async, but binary wheels less consistent across platforms
- `sqlalchemy`: ORM overhead not needed for a small 1-table schema

---

## Decision 3: Export File Format

**Decision**: JSON Lines (`.jsonl`) — one JSON object per document per line

**Rationale**:
- Human-readable and self-describing (each line is a complete document)
- Streaming-compatible: can be written and read line-by-line without loading corpus into memory
- Universally supported (any editor, jq, Python json module)
- Corpus of 293 docs at ~50KB avg = ~14MB export — reasonable text file size

**Format**:
```json
{"source_id": "docs/my-guide.md", "title": "My Guide", "content": "...", "fingerprint": "abc123...", "version": 1, "created_at": "2026-03-07T10:00:00Z", "updated_at": "2026-03-07T10:00:00Z"}
```

**Alternatives considered**:
- CSV: Poor for multi-line text content
- SQLite dump: Binary, not portable without SQLite
- JSON array: Requires loading entire file into memory for large corpora

---

## Decision 4: Constitution Violation Justification

**Violation**: Constitution Section "Data Persistence" states "No separate database — ChromaDB is single source of truth".

**Justification (REQUIRED)**:

ChromaDB alone cannot satisfy the requirements of this spec:

1. **Reindexing** (FR-006): ChromaDB stores chunk text in document content fields. Reindexing requires re-reading original full documents, not individual chunks. There is no efficient "get all documents by source_id in insertion order" API in ChromaDB that reassembles full text reliably.

2. **Export/Import** (FR-004, FR-005): ChromaDB's export is the raw ChromaDB collection — it cannot be migrated to a system with a different embedding model without re-embedding. A Postgres document store decouples full content from embeddings, enabling content-first export/import with re-embedding on import.

3. **Document lifecycle** (FR-007, FR-008): ChromaDB has no versioning concept. Tracking document versions requires an external store.

4. **Content size**: ChromaDB metadata fields are serialized as strings in the SQLite backing store. Large documents (>100KB markdown files) stored across many chunks are not efficiently reassembled from metadata.

**Constitution Amendment Required**: Section "Data Persistence" must be updated to reflect the dual-store architecture. This is documented in the plan complexity tracking.

---

## Decision 5: Postgres Schema

**Decision**: Single table `memoria_documents` in a dedicated `memoria` database (separate from workdiary's `workdiary` database, same Postgres instance).

```sql
CREATE TABLE IF NOT EXISTS memoria_documents (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id    TEXT        NOT NULL UNIQUE,
    title        TEXT        NOT NULL,
    content      TEXT        NOT NULL,
    fingerprint  TEXT        NOT NULL,  -- SHA-256 hex of strip(content)
    version      INTEGER     NOT NULL DEFAULT 1,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    active       BOOLEAN     NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_memoria_docs_source ON memoria_documents(source_id);
CREATE INDEX IF NOT EXISTS idx_memoria_docs_fingerprint ON memoria_documents(fingerprint);
```

**Rationale**:
- `source_id` is the natural key (e.g., "docs/my-guide.md" or any user-provided stable string)
- `fingerprint` enables O(1) change detection for idempotent imports
- `active` flag allows soft-delete for safety (can be hard-deleted or retained for audit)
- Single table keeps the adapter simple — no joins, no complex queries

---

## Decision 6: DocumentStorePort Interface

**Decision**: New port `DocumentStorePort` in `memoria/domain/ports/document_store.py`.

```python
class DocumentStorePort(Protocol):
    def store(self, source_id: str, title: str, content: str) -> StoredDocument: ...
    def get(self, source_id: str) -> StoredDocument | None: ...
    def list_all(self) -> list[StoredDocument]: ...
    def delete(self, source_id: str) -> bool: ...
    def get_fingerprint(self, source_id: str) -> str | None: ...
    def export_all(self) -> Iterator[StoredDocument]: ...
    def count(self) -> int: ...
```

**Rationale**:
- Follows existing port pattern (Protocol class, no inheritance)
- Minimal surface area — only operations the use cases require
- `export_all()` returns an iterator for streaming export without loading corpus into memory

---

## Decision 7: Backward Compatibility Strategy

**Decision**: All existing `skill_helpers.py` public functions remain unchanged. New functions are additive.

| Existing (unchanged) | New (additive) |
|---------------------|----------------|
| `search_knowledge()` | `store_document(content, source_id, title)` |
| `add_document(file_path, reindex)` | `get_document(source_id)` |
| `index_documents(pattern, rebuild)` | `delete_document(source_id)` |
| `list_indexed_documents()` | `list_documents()` |
| `get_stats()` | `export_corpus(output_path)` |
| `health_check()` | `import_corpus(input_path)` |
| | `reindex_corpus()` |
| | `migrate_from_docs_folder(docs_dir)` |

`add_document()` and `index_documents()` are updated internally to also write to Postgres — the signatures and outputs are unchanged.

---

## Decision 8: MCP Adapter

**Decision**: Implement `memoria/adapters/mcp/server.py` as a FastMCP server exposing `search_knowledge` and `get_document` tools.

**Rationale**:
- The `memoria/adapters/mcp/` folder was created but left empty — this is the natural home
- Two tools directly maps to user's requirement: "chunks from one MCP tool, full document from another"
- FastMCP is already used in the ecosystem (chronos-mcp-server uses it)

**New dependencies**: `fastmcp>=0.1.0` or use `mcp` package directly (check compatibility with existing memoria-mcp server)

**Note**: This is a local STDIO MCP server. The existing HTTP MCP server in `claude_infra` is a separate deployment artifact that wraps this.

---

## Decision 9: Embedding Adapter Strategy

**Decision**: Both `OllamaEmbeddingAdapter` (new) and `SentenceTransformerAdapter` (existing) implement `EmbeddingGeneratorPort`. Runtime config (`MEMORIA_EMBEDDING_ADAPTER` env var) selects which is active. Default: `ollama`.

**Rationale**:
- All embedding must run on relishhost2 (Ollama) — no local model. `OllamaEmbeddingAdapter` is the production adapter.
- `SentenceTransformerAdapter` is preserved as a fallback/alternative — no removal, no disruption to existing tests or code that imports it.
- Port abstraction makes this a clean swap: callers only see `EmbeddingGeneratorPort`, not the implementation.

**Alternatives considered**:
- **Replace SentenceTransformerAdapter entirely**: Simpler, but discards a working tested adapter. If relishhost2 is unavailable, system has no fallback.
- **Single adapter with optional remote**: Adds complexity to a single class — rejected in favour of clean separation.

---

## Decision 10: Ollama Embedding Model

**Decision**: `mxbai-embed-large` (1024-dimension vectors), default model for `OllamaEmbeddingAdapter`.

**Rationale**:
- 1024-dim vectors provide higher embedding quality than 384-dim all-MiniLM-L6-v2 for RAG retrieval tasks
- `mxbai-embed-large` is available on relishhost2's Ollama instance (provisioned via localLab spec 019)
- Model name configurable via `MEMORIA_OLLAMA_MODEL` — can switch without code change

**Implication**: Switching embedding adapters (Ollama ↔ sentence_transformers) produces incompatible vector dimensions (1024 vs 384). Switching requires a `reindex_corpus()` call to regenerate all chunks with the new adapter's dimensions. This is enforced by FR-016.

---

## Decision 11: Ollama HTTP Client

**Decision**: `ollama` Python library (`pip install ollama`) for `OllamaEmbeddingAdapter`.

**Rationale**:
- Official client maintained by Ollama team — handles connection management, error handling, and API versioning
- Clean API: `ollama.embeddings(model="mxbai-embed-large", prompt=text)` — no boilerplate
- Avoids writing raw HTTP code against the Ollama REST API

**Alternatives considered**:
- `httpx`: Direct REST calls to `POST /api/embeddings` — works, but adds boilerplate and re-implements what the official library provides
- `requests`: Same as above, synchronous, but less clean

---

## Decision 12: Testing Strategy — Stubs vs Live Services

**Decision**: Unit tests use in-memory port stubs (`DocumentStoreStub`, `EmbeddingStub`, `VectorStoreStub`). Integration tests (`@pytest.mark.integration`) written but skipped by default until relishhost1/relishhost2 infrastructure is provisioned.

**Rationale**:
- All business logic is expressible through port interfaces — stubs provide full coverage of skill_helpers.py logic without external services
- Infrastructure (Postgres, ChromaDB, Ollama) is on remote hosts not yet provisioned at time of writing code
- Integration tests ARE written (not deferred in code) — deferred only in execution. `conftest.py` skips them unless `--run-integration` flag is passed
- This follows the onion architecture principle: business logic should not depend on infrastructure

**Stub implementations**:
- `DocumentStoreStub`: in-memory dict, implements all `DocumentStorePort` methods
- `EmbeddingStub`: returns deterministic zero vectors of configurable dimension (default 1024, matching mxbai-embed-large)
- `VectorStoreStub`: in-memory list with simple cosine similarity for search
