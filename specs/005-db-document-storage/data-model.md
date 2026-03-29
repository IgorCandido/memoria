# Data Model: DB-Backed Document Storage & Reindex API

**Feature**: 005-db-document-storage
**Phase**: 1 - Design

---

## Domain Entities (New)

### StoredDocument

The authoritative record of a document in the system. Lives in Postgres.

```python
@dataclass(frozen=True)
class StoredDocument:
    source_id: str        # Natural key — stable user-provided identifier (e.g. "docs/my-guide.md")
    title: str            # Human-readable title
    content: str          # Full original text content
    fingerprint: str      # SHA-256 hex of strip(content) — for change detection
    version: int          # Incremented on each update (starts at 1)
    created_at: datetime  # UTC timestamp of first storage
    updated_at: datetime  # UTC timestamp of last update
    id: str = ""          # UUID from Postgres (empty before first persist)
```

**Invariants**:
- `source_id` must be non-empty, strip()-clean
- `title` must be non-empty
- `content` must be non-empty
- `fingerprint` must be 64-char hex string (SHA-256)
- `version` >= 1
- `created_at <= updated_at`

---

### ExportManifest

Metadata header written to the first line of an export file.

```python
@dataclass(frozen=True)
class ExportManifest:
    exported_at: datetime  # UTC timestamp of export
    document_count: int    # Total documents in export
    system_version: str    # Memoria version at time of export
    format_version: str    # Export format version (e.g. "1.0")
```

---

### ImportResult

Summary of an import operation.

```python
@dataclass(frozen=True)
class ImportResult:
    documents_added: int    # New documents inserted
    documents_updated: int  # Existing documents updated (fingerprint changed)
    documents_skipped: int  # Skipped — unchanged (fingerprint match)
    documents_failed: int   # Failed with error
    errors: tuple[tuple[str, str], ...]  # ((source_id, error_message), ...)
    duration_seconds: float
```

---

### ReindexResult

Summary of a reindex (re-embed) operation.

```python
@dataclass(frozen=True)
class ReindexResult:
    documents_processed: int
    chunks_created: int
    documents_failed: int
    errors: tuple[tuple[str, str], ...]  # ((source_id, error_message), ...)
    duration_seconds: float
    embedding_model: str  # e.g. "all-MiniLM-L6-v2"
```

---

## New Port

### DocumentStorePort

```python
# memoria/domain/ports/document_store.py

class DocumentStorePort(Protocol):

    def store(self, source_id: str, title: str, content: str) -> StoredDocument:
        """Insert or update a document. Upsert by source_id. Increments version on update."""
        ...

    def get(self, source_id: str) -> StoredDocument | None:
        """Retrieve full document by source_id. Returns None if not found."""
        ...

    def list_all(self) -> list[StoredDocument]:
        """Return all active documents (without content for efficiency)."""
        ...

    def delete(self, source_id: str) -> bool:
        """Soft-delete document. Returns True if deleted, False if not found."""
        ...

    def get_fingerprint(self, source_id: str) -> str | None:
        """Return fingerprint of stored document, or None if not found. Fast path for change detection."""
        ...

    def export_all(self) -> Iterator[StoredDocument]:
        """Stream all active documents with full content. Memory-efficient."""
        ...

    def count(self) -> int:
        """Return count of active documents."""
        ...

    def health_check(self) -> bool:
        """Return True if store is reachable and operational."""
        ...
```

---

## New Adapter

### PostgresDocumentStoreAdapter

```
memoria/adapters/postgres/
├── __init__.py
└── postgres_document_store_adapter.py
```

**Key responsibilities**:
- Manage Postgres connection (psycopg2-binary)
- Create `memoria_documents` table on first use (idempotent DDL)
- Implement all `DocumentStorePort` methods
- Compute SHA-256 fingerprint on `store()`
- Upsert logic: if source_id exists and fingerprint changed → update + increment version; if fingerprint unchanged → return existing (no write)

---

## New Embedding Adapter

### OllamaEmbeddingAdapter

```
memoria/adapters/ollama/
├── __init__.py
└── ollama_embedding_adapter.py
```

**Implements**: `EmbeddingGeneratorPort`

**Key responsibilities**:
- Use `ollama` Python library to call Ollama REST API on relishhost2
- `embed_text(text: str) → list[float]` — single embedding via `ollama.embeddings(model=..., prompt=text)`
- `embed_texts_batch(texts: list[str]) → list[list[float]]` — sequential calls (Ollama handles batching internally)
- Read `MEMORIA_OLLAMA_HOST`, `MEMORIA_OLLAMA_PORT`, `MEMORIA_OLLAMA_MODEL` from env vars
- Active when `MEMORIA_EMBEDDING_ADAPTER=ollama` (default)

**Coexists with**: `SentenceTransformerAdapter` (existing, unchanged) — both implement `EmbeddingGeneratorPort`

---

## Test Stubs

### DocumentStoreStub

```
memoria/adapters/stubs/
└── document_store_stub.py
```

In-memory dict implementation of `DocumentStorePort`. No external dependencies. Used in all unit tests.

### EmbeddingStub

```
memoria/adapters/stubs/
└── embedding_stub.py
```

In-memory implementation of `EmbeddingGeneratorPort`. Returns deterministic zero vectors. Configurable dimension (default 1024 to match `mxbai-embed-large`). Used in all unit tests.

### VectorStoreStub

```
memoria/adapters/stubs/
└── vector_store_stub.py
```

In-memory list implementation of `VectorStorePort`. Supports add, search (simple cosine similarity), and delete operations. Used in all unit tests.

---

## New MCP Adapter

### MCP Server

```
memoria/adapters/mcp/
├── __init__.py
└── server.py          # FastMCP STDIO server
```

**Tools exposed**:

| Tool | Arguments | Returns |
|------|-----------|---------|
| `search_knowledge` | `query: str, mode: str, limit: int` | Formatted chunk results string |
| `get_document` | `source_id: str` | Full document content string |

---

## Postgres Schema

```sql
-- Database: memoria (separate from workdiary database, same Postgres instance on port 5435)

CREATE TABLE IF NOT EXISTS memoria_documents (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id    TEXT        NOT NULL UNIQUE,
    title        TEXT        NOT NULL,
    content      TEXT        NOT NULL,
    fingerprint  TEXT        NOT NULL,
    version      INTEGER     NOT NULL DEFAULT 1,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    active       BOOLEAN     NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_memoria_docs_source ON memoria_documents (source_id) WHERE active = TRUE;
CREATE INDEX IF NOT EXISTS idx_memoria_docs_fingerprint ON memoria_documents (fingerprint) WHERE active = TRUE;
```

---

## Updated Source Structure

```text
memoria/
├── domain/
│   ├── entities.py                          # + StoredDocument, ExportManifest, ImportResult, ReindexResult
│   └── ports/
│       ├── document_store.py                # NEW: DocumentStorePort
│       ├── vector_store.py                  # existing
│       ├── embedding_generator.py           # existing
│       ├── search_engine.py                 # existing
│       └── document_processor.py           # existing
├── adapters/
│   ├── postgres/                            # NEW
│   │   ├── __init__.py
│   │   └── postgres_document_store_adapter.py
│   ├── mcp/                                 # IMPLEMENT (was empty)
│   │   ├── __init__.py
│   │   └── server.py
│   ├── stubs/
│   │   └── document_store_stub.py           # NEW: test stub for DocumentStorePort
│   ├── chromadb/                            # existing
│   ├── sentence_transformers/               # existing
│   ├── search/                              # existing
│   └── document/                            # existing
├── skill_helpers.py                         # + store_document, get_document, delete_document,
│                                            #   list_documents, export_corpus, import_corpus,
│                                            #   reindex_corpus, migrate_from_docs_folder
└── ...

tests/
├── adapters/
│   └── postgres/                            # NEW
│       └── test_postgres_document_store_adapter.py
├── ports/
│   └── test_document_store_port.py          # NEW
├── adapters/stubs/
│   └── test_document_store_stub.py          # NEW
├── acceptance/
│   └── test_document_management.py          # NEW: end-to-end acceptance tests
└── test_skill_helpers.py                    # EXTEND: test new public functions
```

---

## Relationships

```
skill_helpers.py
    │
    ├─ _get_adapters()  ─────────────────────────────────────────────────────────┐
    │                                                                             │
    │   _get_document_store()  ──→  PostgresDocumentStoreAdapter                 │
    │                                    │                                        │
    │                                    └──→ Postgres: memoria_documents table   │
    │                                                                             │
    │   (existing adapters)  ─────────────────────────────────────────────────── ┘
    │       ChromaDBAdapter  ──→ ChromaDB (port 8001)
    │       SentenceTransformerAdapter
    │       SearchEngineAdapter
    │       DocumentProcessorAdapter
    │
    ├─ store_document(content, source_id, title)
    │       1. PostgresDocumentStoreAdapter.store(source_id, title, content)
    │       2. DocumentProcessorAdapter.process_document(content)
    │       3. SentenceTransformerAdapter.embed_batch(chunks)
    │       4. ChromaDBAdapter.add_documents(docs_with_embeddings)
    │       [old chunks for source_id deleted before step 4]
    │
    ├─ get_document(source_id)
    │       1. PostgresDocumentStoreAdapter.get(source_id)
    │       2. Return StoredDocument.content
    │
    ├─ reindex_corpus()
    │       1. PostgresDocumentStoreAdapter.export_all()  [stream]
    │       2. ChromaDBAdapter.clear()
    │       3. For each document: chunk → embed → add to ChromaDB
    │
    └─ export_corpus(output_path)
            1. Write ExportManifest as first line
            2. PostgresDocumentStoreAdapter.export_all()  [stream to file]
```
