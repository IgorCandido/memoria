# Quickstart: 005-db-document-storage

## Prerequisites

- Infrastructure provisioned via localLab spec `019-memoria-infrastructure`:
  - Postgres running on relishhost1:5435 (`memoria` database exists)
  - ChromaDB running on relishhost1:8001
  - `mxbai-embed-large` model pulled on relishhost2:11434 Ollama
- Shared venv activated: `source /Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/activate`

## Verify Infrastructure

```bash
# Postgres reachable and memoria database exists
psql -h relishhost1 -p 5435 -U postgres -c "\l" | grep memoria

# ChromaDB heartbeat
curl http://relishhost1:8001/api/v1/heartbeat

# Ollama mxbai-embed-large available (returns 1024-element array)
curl http://relishhost2:11434/api/embeddings \
  -d '{"model":"mxbai-embed-large","prompt":"test"}' | python3 -c \
  "import sys,json; e=json.load(sys.stdin)['embedding']; print(f'OK: {len(e)} dims')"
```

## Setup

```bash
# 1. Install new dependencies
pip install psycopg2-binary ollama

# 2. Set environment (or export in shell profile)
export MEMORIA_PG_HOST=relishhost1
export MEMORIA_PG_PORT=5435
export MEMORIA_PG_DATABASE=memoria
export MEMORIA_PG_USER=postgres
export MEMORIA_CHROMA_HOST=relishhost1
export MEMORIA_CHROMA_PORT=8001
export MEMORIA_OLLAMA_HOST=relishhost2
export MEMORIA_OLLAMA_PORT=11434
export MEMORIA_OLLAMA_MODEL=mxbai-embed-large
export MEMORIA_EMBEDDING_ADAPTER=ollama

# 3. Run schema migration (auto-runs on first adapter use, or manually)
python -c "
from memoria.adapters.postgres.postgres_document_store_adapter import PostgresDocumentStoreAdapter
import os
a = PostgresDocumentStoreAdapter(
    host=os.getenv('MEMORIA_PG_HOST', 'relishhost1'),
    port=int(os.getenv('MEMORIA_PG_PORT', '5435')),
    database=os.getenv('MEMORIA_PG_DATABASE', 'memoria'),
    user=os.getenv('MEMORIA_PG_USER', 'postgres')
)
a._ensure_schema()
print('Schema ready')
"
```

## Core API Usage

```python
from memoria.skill_helpers import (
    store_document, get_document, delete_document, list_documents,
    export_corpus, import_corpus, reindex_corpus, migrate_from_docs_folder
)

# Store a document (no file needed)
store_document(
    content="# My Guide\nThis is my guide content...",
    source_id="guides/my-guide",
    title="My Guide"
)

# Retrieve full document
doc = get_document("guides/my-guide")
print(doc)  # Returns full content string

# Search (unchanged — returns chunks embedded via mxbai-embed-large)
from memoria.skill_helpers import search_knowledge
results = search_knowledge("my guide content")
print(results)

# List all documents
docs = list_documents()
for d in docs:
    print(f"{d.source_id} v{d.version} ({len(d.content)} chars)")

# Delete
delete_document("guides/my-guide")
```

## Export / Import

```bash
# Export entire corpus
python -c "
from memoria.skill_helpers import export_corpus
export_corpus('/tmp/memoria-export.jsonl')
print('Export complete')
"

# Import on a clean system
python -c "
from memoria.skill_helpers import import_corpus
result = import_corpus('/tmp/memoria-export.jsonl')
print(f'Added: {result.documents_added}, Updated: {result.documents_updated}, Failed: {result.documents_failed}')
"
```

## Reindex (after embedding model change)

```bash
python -c "
from memoria.skill_helpers import reindex_corpus
result = reindex_corpus()
print(f'Reindexed {result.documents_processed} docs, {result.chunks_created} chunks ({result.embedding_model}) in {result.duration_seconds:.1f}s')
"
```

## Legacy Migration (one-time)

```bash
python -c "
from memoria.skill_helpers import migrate_from_docs_folder
result = migrate_from_docs_folder('/Users/igorcandido/Github/thinker/memoria/main/memoria/docs')
print(f'Migrated: {result.documents_added} new, {result.documents_skipped} already current')
"
```

## Running Tests

```bash
cd /Users/igorcandido/Github/thinker/memoria/main

# Unit tests (no external services — uses in-memory stubs)
pytest tests/unit/ -v

# Integration tests (requires relishhost1 + relishhost2 infrastructure)
pytest tests/integration/ -v --run-integration

# Full suite (unit only by default)
pytest tests/ -v
```

## Switching Embedding Adapter

```bash
# Use Ollama on relishhost2 (default, 1024 dims)
export MEMORIA_EMBEDDING_ADAPTER=ollama

# Use local SentenceTransformer (384 dims — requires reindex after switch)
export MEMORIA_EMBEDDING_ADAPTER=sentence_transformers

# After switching adapter, reindex is required:
python -c "from memoria.skill_helpers import reindex_corpus; reindex_corpus()"
```

## MCP Server (Local STDIO)

```bash
# Run the local STDIO MCP server (exposes search_knowledge + get_document)
python -m memoria.adapters.mcp.server
```

## Environment Variables

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
| `MEMORIA_OLLAMA_MODEL` | `mxbai-embed-large` | Embedding model (1024 dims) |
| `MEMORIA_EMBEDDING_ADAPTER` | `ollama` | Active adapter: `ollama` or `sentence_transformers` |
| `MEMORIA_DEBUG` | `` | Enable debug output |
