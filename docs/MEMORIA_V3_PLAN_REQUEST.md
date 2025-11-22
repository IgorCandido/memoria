# Memoria v3.0 Architecture Plan - User Requirements

**Date**: 2025-11-09
**Status**: Pending Implementation (after v3.0.0 UAT completion)

---

## User Request

> after all user acceptance tests are running green [...] I want to you switch to planning mode and scope based on industry standards and what i got chatgpt to produce plan wise, do not follow it to the t if industry standards deviate we need to talk about it, but use it as an guide that is also my opinion on how to improve and create memoria version 3. This will be work carried out on a branch called memoria 3. Give me a plan in plan mode for all this

---

## ChatGPT-Produced Plan (User's Guide)

### Architecture Overview

Components:

```
Client → MCP →
   ├─ Query → Chroma → returns top-K chunks + metadata → MCP caller
   ├─ Fetch full document → Postgres
   └─ Ingest / Update → Postgres (document metadata & content) → Chroma (chunks)
```

* **Postgres**: stores all full document content + metadata (NO pgvector)
* **Chroma**: stores chunks with embeddings + metadata for semantic search
* **MCP**: orchestrates queries, update propagation, and document retrieval
* **Optional reranker**: cross-encoder or LLM-based score for chunk ranking, returns scores only

### Key Principles

1. **Postgres** is the single source of truth for full documents and metadata. No pgvector.
2. **Chroma** handles embeddings and vector search for chunks. Each chunk stores its text and metadata in Chroma; full content never leaves Postgres.
3. **Chunks** are only in Chroma, not in Postgres. Postgres stores document metadata, versioning, timestamps, external ids, and the full content.
4. **MCP calls** receive chunks (from Chroma) and can fetch the full document via Postgres if needed.
5. **Update and reindexing** workflows propagate to Chroma.

---

## Data Model

### Postgres (documents table)

```sql
CREATE TABLE documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id TEXT UNIQUE,
  title TEXT,
  content TEXT NOT NULL,
  version INT DEFAULT 1,
  fingerprint TEXT,             -- sha256 of normalized content
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  is_active BOOLEAN DEFAULT TRUE
);
```

**Notes:**
* All full content is in `content`.
* Fingerprint used to detect changes.
* Versioning allows chunk propagation updates.

### Chroma (chunks collection)

For each chunk:

```json
{
  "id": "uuid-chunk",
  "document_id": "uuid-document",
  "external_chunk_id": "optional-external-id",
  "title": "optional title",
  "text": "chunk text",
  "start_char": 1024,
  "end_char": 1560,
  "metadata": {
    "document_id": "uuid-document",
    "external_id": "external-doc-id",
    "version": 2,
    "created_at": "timestamp",
    "updated_at": "timestamp"
  },
  "embedding": [vector floats...]
}
```

* **Chunk text stored in Chroma only**.
* Metadata includes references back to the Postgres document.
* MCP can retrieve full document by `document_id` from Postgres.

---

## Ingest & Update Pipeline

1. **Normalize** document content (strip formatting, extract text).
2. **Compute fingerprint** (`sha256(normalized_text)`)
3. **Insert or update** document in Postgres:
   * If new: version = 1
   * If changed: bump version, update timestamps
4. **Chunking:**
   * Deterministic or optional LLM-assisted semantic chunking
   * Target 400–800 tokens per chunk, overlap 50–150 tokens
5. **Upsert chunks to Chroma:**
   * For each chunk, compute embedding (embedding model)
   * Include metadata (`document_id`, `external_id`, version, timestamps)
   * Remove or mark obsolete chunks in Chroma for previous version

**Update workflow:**
* Compute fingerprint for new content → compare
* If changed: generate new chunks → insert/update in Chroma → mark old chunks inactive
* Keep full content in Postgres for reference

**Reindex workflow:**
* Force recompute chunks for a document or corpus
* Deduplicate chunks by similarity / hash
* Optionally merge near-duplicate docs → create new doc in Postgres → re-chunk

---

## Query Workflow

1. **MCP receives user query**
2. **Generate embedding** using the same embedding model
3. **Query Chroma** → top-K chunks, return `text + metadata` only
4. **Optional reranker** → re-rank top candidates (scores only)
5. **Return to MCP caller** → no LLM synthesis at this stage
6. **Fetch full document** if caller requests (`document_id`) → Postgres returns content

---

## API Surface (MCP endpoints)

* **POST /v1/documents** — ingest new document (Postgres + Chroma chunking)
* **PUT /v1/documents/{document_id}** — update document → propagate to Chroma
* **POST /v1/documents/{document_id}/reindex** — recompute chunks
* **POST /v1/query** — return top-K chunk results from Chroma
* **GET /v1/chunks/{chunk_id}** — return chunk text + metadata
* **GET /v1/documents/{document_id}** — return full document from Postgres

---

## Advantages

* Full content safe in Postgres (single source of truth)
* Chunks in Chroma for fast vector search
* MCP receives raw chunks, avoids LLM hallucination or summarization errors
* Full document retrieval via Postgres for completeness
* Versioning + timestamps allow incremental updates and chunk propagation
* Reindexing allows merge / split / dedup workflows

---

## Next Steps (from ChatGPT)

* Build ingestion pipeline: Postgres insert/update → Chroma chunk upsert
* Query service: MCP calls embedding → Chroma → return top-K chunks
* Reindex/update service: detect document change → update Chroma chunks
* Optional: reranker service (scores only)

---

## User's Additional Notes

> If you want, I can now **produce a concrete Python + Chroma + Postgres FastAPI skeleton** that implements ingestion, query, full-doc retrieval, and reindexing according to this design. This would be ready to drop into MCP and Memoria.

**User wants**: Comprehensive plan in plan mode, following industry standards, deviating from ChatGPT plan only when standards require it (with discussion).

**Branch**: `memoria-v3`

**Deliverable**: Extensive plan document covering:
- Architecture alignment with industry standards
- Data model refinements
- API design
- Migration strategy from v3.0.0 → v3.x
- Implementation phases
- Testing strategy
- Performance considerations

---

## Current Blocker

Must complete v3.0.0 UAT tests first (get all 18 scenarios passing) before starting v3.x planning and implementation.
