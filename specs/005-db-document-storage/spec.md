# Feature Specification: DB-Backed Document Storage & Reindex API

**Feature Branch**: `005-db-document-storage`
**Created**: 2026-02-11
**Status**: Draft
**Input**: Transition memoria from filesystem-dependent (/docs folder) ingestion to a fully database-backed document management system. All client interactions go through API — no filesystem interface. Support export, import, and reindex for embedding model changes.

## Background

Memoria currently relies on a `/docs` filesystem directory as the source of truth for document content. Indexing reads files from `/docs`, chunks them, embeds them, and writes chunks to ChromaDB. To retrieve full document content, the system must access the filesystem. This creates a tight coupling to the local filesystem that prevents:

- Portability: cannot move or replicate the system without copying the `/docs` folder
- Reindexing: when the embedding model changes (spec 004), there is no way to re-embed all documents without the original files present
- Document lifecycle management: no way to track, version, or delete documents through a clean API
- Export/import: no way to dump the full corpus for backup or migration without filesystem access

The goal is to introduce a durable document store (Postgres) as the single source of truth for full document content and metadata. ChromaDB remains the vector store for chunks and embeddings only. All client operations go through a Python API — no client ever reads or writes the filesystem directly.

## Dependencies

- **Spec 004 (Configurable Embeddings)**: Changing embedding models requires reindexing the entire corpus. This spec provides the reindex interface that spec 004 depends on.
- **localLab infrastructure spec**: Postgres, ChromaDB (relishhost1), and Ollama (relishhost2) must be provisioned via Ansible before integration tests can run. A Speckit spec.md in `~/Github/thinker/localLab` defines this provisioning — out of scope for this feature but a hard prerequisite for integration testing.
- **Existing infrastructure**: Postgres on relishhost1 (Docker, configurable via env vars). ChromaDB on relishhost1 (Docker, configurable via env vars). Ollama embedding service on relishhost2 (configurable via env vars). No infrastructure runs locally on the development machine — all services are remote.
- **Current architecture**: Onion Architecture with ports/adapters pattern — this is a clean extension via new ports and adapters.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Store Documents in Database (Priority: P1)

As a memoria operator, I want to add documents to the system through an API call that stores the full content in a database, so that I no longer depend on a `/docs` folder and all document data is durably persisted in one place.

**Why this priority**: Foundation for everything else. Without database-backed storage, export/import/reindex cannot function. This replaces the filesystem dependency entirely.

**Independent Test**: Call the document ingestion API with a text document, verify it is stored in the database with metadata, chunked, embedded, and searchable via `search_knowledge()` — all without any `/docs` folder existing.

**Acceptance Scenarios**:

1. **Given** an empty system with no `/docs` folder, **When** a document is submitted via the API with title, content, and optional metadata, **Then** the full content is stored in the document store, chunks are created in ChromaDB, and the document is searchable
2. **Given** a document already stored, **When** the same document is submitted again with updated content, **Then** the version is incremented, old chunks are replaced with new ones, and the full content is updated
3. **Given** a document stored in the database, **When** a user searches for content within it, **Then** search returns relevant chunks with metadata linking back to the source document
4. **Given** a stored document, **When** a user requests the full document by ID, **Then** the complete original content is returned from the database (not from filesystem)

---

### User Story 2 - Export Full Corpus to File (Priority: P1)

As a memoria operator, I want to export all documents from the database to a portable file, so that I can back up my knowledge base, migrate it to another system, or prepare for a reindex operation.

**Why this priority**: Export is a prerequisite for safe reindexing and disaster recovery. Without export, changing the embedding model or recovering from data loss is impossible.

**Independent Test**: Populate the system with several documents via API, call the export function, verify the output file contains all documents with their full content and metadata in a portable format.

**Acceptance Scenarios**:

1. **Given** a system with 293 documents stored, **When** an export is requested, **Then** a single file is produced containing all documents with full content, metadata, and version information
2. **Given** an export file, **When** opened in a text editor or parsed programmatically, **Then** the format is human-readable and self-describing (JSON lines or similar)
3. **Given** a system with no documents, **When** an export is requested, **Then** an empty (but valid) export file is produced with appropriate messaging
4. **Given** an export in progress on a large corpus, **When** the operation runs, **Then** progress is reported and the operation completes without timeouts

---

### User Story 3 - Import and Batch Re-import from File (Priority: P1)

As a memoria operator, I want to import documents from an export file into the system, so that I can restore a backup, migrate from another instance, or re-populate after a reindex.

**Why this priority**: Import completes the export/import cycle and is required for the reindex workflow. A system that can export but not import is incomplete.

**Independent Test**: Take an export file, call the import function on a clean system, verify all documents are stored in the database and all chunks are created in ChromaDB with correct embeddings.

**Acceptance Scenarios**:

1. **Given** a valid export file with 293 documents, **When** imported into an empty system, **Then** all documents are stored in the database and all chunks are embedded and searchable in ChromaDB
2. **Given** an export file and a system with existing documents, **When** imported, **Then** documents are upserted (new ones added, existing ones updated based on fingerprint matching)
3. **Given** a large import (293 docs, ~17K resulting chunks), **When** import runs, **Then** progress is reported and the operation completes using batched processing
4. **Given** a corrupted or invalid export file, **When** import is attempted, **Then** the operation fails with a clear error and no partial data is left in an inconsistent state

---

### User Story 4 - Reindex All Documents (Priority: P2)

As a memoria operator, I want to reindex the entire corpus when the embedding model changes, so that all chunks are re-embedded with the new model and search continues to work correctly.

**Why this priority**: Directly enables spec 004 (configurable embeddings). Without reindex, changing the embedding model produces a broken search index with incompatible vectors.

**Independent Test**: Store documents in the system, trigger a reindex, verify all ChromaDB chunks are regenerated with fresh embeddings while the source documents in the database remain unchanged.

**Acceptance Scenarios**:

1. **Given** a system with 293 documents and 17K chunks, **When** reindex is triggered, **Then** all documents are re-read from the database, re-chunked, re-embedded with the current model, and the ChromaDB collection is replaced
2. **Given** a reindex in progress, **When** the operation is interrupted, **Then** the system either completes atomically or rolls back cleanly — no partial/corrupt index remains
3. **Given** a reindex completes, **When** a search is performed, **Then** results use the new embeddings and search quality reflects the new model
4. **Given** the embedding model is changed (spec 004), **When** reindex is triggered, **Then** the new model is used for all embeddings and ChromaDB metadata reflects the new dimensions

---

### User Story 5 - Document Lifecycle Management (Priority: P2)

As a memoria operator, I want to list, inspect, and delete documents through the API, so that I can manage the knowledge base without touching the filesystem.

**Why this priority**: Completes the API-only interface by providing CRUD operations for document management. Without this, operators cannot remove outdated or incorrect documents.

**Independent Test**: Add several documents, list them, inspect one by ID, delete one, verify it is removed from both the document store and ChromaDB.

**Acceptance Scenarios**:

1. **Given** a system with stored documents, **When** a list operation is requested, **Then** all documents are returned with their ID, title, version, creation date, and chunk count
2. **Given** a document ID, **When** inspect is requested, **Then** full metadata is returned including content size, version history, fingerprint, and chunk count
3. **Given** a document ID, **When** delete is requested, **Then** the document is removed from the database and all its chunks are removed from ChromaDB
4. **Given** a delete operation, **When** the document does not exist, **Then** a clear "not found" response is returned

---

### User Story 6 - Legacy Migration from /docs Folder (Priority: P3)

As a memoria operator migrating from the current system, I want to bulk-import all existing documents from the `/docs` folder into the database, so that I can transition to the new system without losing any knowledge.

**Why this priority**: One-time migration path. Important for adoption but not needed for the core system to function.

**Independent Test**: Point the migration tool at the existing `/docs` folder (293 files), run migration, verify all documents are stored in the database and searchable.

**Acceptance Scenarios**:

1. **Given** a `/docs` folder with 293 markdown/text files, **When** migration is run, **Then** all files are read, stored in the database with original filenames as titles, and indexed into ChromaDB
2. **Given** a migration completes, **When** the `/docs` folder is removed, **Then** the system continues to function normally using only database-backed storage
3. **Given** some documents already exist in the database (previously migrated), **When** migration is run again, **Then** only new or changed documents are processed (idempotent based on fingerprint)

---

### Edge Cases

- What happens when a document exceeds the maximum content size for the database? (Should reject with clear size limit error)
- What happens when ChromaDB is unreachable during import? (Should fail clearly, documents remain in Postgres but unchunked — retry should pick up where it left off)
- What happens when Postgres is unreachable? (All operations should fail with clear connection error)
- What happens during a reindex if one document fails to embed? (Skip the document, log the error, continue with remaining documents, report failures at completion)
- What happens when two concurrent imports run? (Should handle gracefully — either serialize or detect conflict)
- What happens when the export file is larger than available memory? (Use streaming writes/reads, never load the full corpus into memory)
- What happens when importing documents that were exported with a different embedding model? (Documents are stored in Postgres regardless — reindex can be triggered separately to re-embed)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST store full document content in a durable database (not filesystem) with metadata including title, fingerprint, version, and timestamps
- **FR-002**: System MUST provide a Python API for adding documents that accepts content as text (not file paths), stores in database, chunks, embeds, and indexes into ChromaDB
- **FR-003**: System MUST provide a Python API for retrieving full document content by document ID from the database
- **FR-004**: System MUST provide an export function that writes all documents from the database to a portable file format (content + metadata), without filesystem reads
- **FR-005**: System MUST provide an import function that reads a portable file and batch-inserts documents into the database, then chunks and embeds into ChromaDB
- **FR-006**: System MUST provide a reindex function that re-reads all documents from the database, re-chunks, re-embeds with the current model, and replaces the ChromaDB collection
- **FR-007**: System MUST provide list, inspect, and delete operations for documents through the Python API
- **FR-008**: System MUST track document versions — updating a document increments the version and replaces its chunks
- **FR-009**: System MUST compute content fingerprints to detect changes and enable idempotent imports
- **FR-010**: System MUST NOT require a `/docs` folder to function — all core operations (add, search, export, import, reindex) work purely from database
- **FR-011**: System MUST preserve backward compatibility — existing `search_knowledge()` API signature remains unchanged
- **FR-012**: System MUST report progress during long operations (import, export, reindex) using the existing ProgressTracker pattern
- **FR-013**: System MUST handle batch operations efficiently — import and reindex of 293 docs / 17K chunks must use batched processing (not one-at-a-time)
- **FR-014**: System MUST provide a one-time migration function to import existing `/docs` folder contents into the database
- **FR-015**: Both `OllamaEmbeddingAdapter` and `SentenceTransformerAdapter` MUST implement `EmbeddingGeneratorPort`; runtime config (`MEMORIA_EMBEDDING_ADAPTER` env var) selects which adapter is active
- **FR-016**: `OllamaEmbeddingAdapter` MUST use model `mxbai-embed-large` by default (1024-dimension vectors); model name configurable via `MEMORIA_OLLAMA_MODEL`. ChromaDB collection MUST be created with matching dimensionality — switching embedding adapters requires a reindex (FR-006)
- **FR-017**: `OllamaEmbeddingAdapter` MUST use the `ollama` Python library (`pip install ollama`) to call the Ollama REST API on relishhost2

### Non-Functional Requirements

- **NFR-001**: Export/import file format MUST be human-readable and self-describing
- **NFR-002**: Import and reindex MUST use streaming/batched I/O — never load full corpus into memory
- **NFR-003**: All new components MUST follow the existing onion architecture (domain ports, adapters, use cases)
- **NFR-004**: Reindex MUST be atomic — either completes fully or leaves the previous index intact

### Key Entities

- **Document**: Full document content with metadata — ID, title, content, version, fingerprint (SHA-256 of normalized content), creation timestamp, update timestamp, active status. This is the single source of truth.
- **DocumentVersion**: Historical record of document changes — tracks version number, timestamp, and fingerprint for each update.
- **ExportManifest**: Metadata about an export file — export timestamp, document count, system version, embedding model active at time of export.
- **ImportResult**: Summary of an import operation — documents added, updated, skipped, failed, with per-document error details.
- **ReindexResult**: Summary of a reindex operation — documents processed, chunks created, failures, duration, embedding model used.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Documents can be added, searched, retrieved, and deleted through the API without any `/docs` folder present on the filesystem
- **SC-002**: Full corpus export (293 documents) produces a valid portable file that can be imported into a clean system with 100% document recovery
- **SC-003**: Import of 293 documents with ~17K resulting chunks completes using batched processing with progress reporting
- **SC-004**: Reindex of full corpus completes with all chunks re-embedded — search returns results using new embeddings after reindex
- **SC-005**: Document updates are versioned — updating a document increments version and old chunks are fully replaced
- **SC-006**: Zero breaking changes to existing `search_knowledge()` API — all current consumers continue to work
- **SC-007**: Legacy migration from `/docs` folder imports all 293 existing documents into the database successfully
- **SC-008**: Interrupted reindex leaves the system in a consistent state — either old index intact or new index complete, never partial

## Testing Approach

- All business logic tests use **port/adapter test doubles** — in-memory classes implementing the domain ports (`DocumentStorePort`, `EmbeddingGeneratorPort`, `VectorStorePort`, etc.). No mocks against real services in unit tests.
- **Integration tests** (adapter tests against real Postgres, ChromaDB, Ollama) are written but not executed until the relishhost1/relishhost2 infrastructure is confirmed up. They are committed but skipped via `pytest.mark.integration`.
- Test doubles live in `memoria/adapters/stubs/` and are importable by any test.

## Assumptions

- Postgres on relishhost1 is used for document storage — same Docker instance shared with other services, separate `memoria` database. Connection parameters configurable via `MEMORIA_PG_HOST`, `MEMORIA_PG_PORT`, `MEMORIA_PG_DATABASE`, `MEMORIA_PG_USER`, `MEMORIA_PG_PASSWORD`.
- ChromaDB on relishhost1 is used for vector storage. Connection configurable via `MEMORIA_CHROMA_HOST`, `MEMORIA_CHROMA_PORT`.
- Ollama on relishhost2 is the embedding service using model `mxbai-embed-large` (1024-dimension vectors). Connection configurable via `MEMORIA_OLLAMA_HOST`, `MEMORIA_OLLAMA_PORT`, `MEMORIA_OLLAMA_MODEL`. No local embedding model is required.
- Both `OllamaEmbeddingAdapter` (new) and `SentenceTransformerAdapter` (existing) implement `EmbeddingGeneratorPort`. Runtime config selects which to use. Default is `OllamaEmbeddingAdapter` for this deployment.
- No infrastructure services run locally on the development machine — all connections are remote.
- Infrastructure (Postgres, ChromaDB, Ollama) is provisioned separately via a Docker Compose spec in `~/Github/thinker/localLab` — outside this feature's scope.
- The existing chunking strategy (2000-char chunks, 100-char overlap) will be reused for consistency unless changed by a future spec.
- The export file format will be JSON Lines (one JSON object per line) for streaming compatibility and human readability.
- Document content is primarily text (markdown, plain text) — binary formats (images, PDFs) are out of scope for this spec.
- The document fingerprint uses SHA-256 of the normalized (whitespace-trimmed) content for change detection.
- Concurrent access patterns are single-writer (one Claude instance at a time) — distributed locking is not required for this spec

---

## Clarifications

### Session 2026-03-07

- Q: Does Ollama on relishhost2 replace the existing `SentenceTransformerAdapter` entirely, or should both exist as alternative implementations of `EmbeddingGeneratorPort`? → A: Coexist — both adapters implement `EmbeddingGeneratorPort`; runtime config (`MEMORIA_EMBEDDING_ADAPTER`) selects which is active
- Q: What is the Ollama embedding model name on relishhost2? → A: `mxbai-embed-large` (1024-dimension vectors)
- Q: Should adapter class names encode the target host (e.g., `RelishHost1PostgresDocumentStoreAdapter`)? → A: No — `PostgresDocumentStoreAdapter` is correct; "postgresRelishHost1" referred to the Docker container name in the localLab spec, not the adapter class
- Q: What format should the localLab infrastructure spec take? → A: Speckit spec.md created in `~/Github/thinker/localLab` alongside existing specs (localLab is an Ansible codebase for local lab provisioning)
- Q: What HTTP client should `OllamaEmbeddingAdapter` use? → A: `ollama` Python library (official client, `pip install ollama`).
