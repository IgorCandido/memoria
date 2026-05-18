# Memoria - RAG Knowledge Base for Claude Code

**Version**: 3.1.0
**Status**: Production Ready
**Architecture**: Onion Architecture with Domain-Driven Design

Memoria is a lightweight RAG (Retrieval-Augmented Generation) skill that gives Claude Code persistent memory through semantic search over your documents. It replaces heavy MCP server stacks with direct Python execution - 98.7% fewer tokens, 75% less memory.

> Plugin install: `./install-plugin.sh` registers memoria as a Claude Code plugin. Manual setup below covers what the installer does.

## Quick Start

### Prerequisites

- **macOS** (tested on macOS 15+)
- **Python 3.11+** (`python3 --version`)
- **uv** (`uv --version`) — manages venv and entry points
- **PostgreSQL** reachable on `relishhost1:5435` (database `memoria`) — stores full document content
- **ChromaDB** reachable on `relishhost1:8001` (or local Docker, see below) — stores vector embeddings
- **Ollama** reachable on `relishhost2:11434` with `mxbai-embed-large` pulled — generates 1024-dim embeddings (default)
- **Claude Code** installed (`claude --version`)

> Local-only fallback: run ChromaDB in Docker (step 2) and set `MEMORIA_EMBEDDING_ADAPTER=sentence_transformers` to use the in-process 384-dim `all-MiniLM-L6-v2` model. You still need Postgres reachable somewhere — point `MEMORIA_PG_*` at it.

### 1. Clone the Repository

```bash
# Clone as bare repo (supports git worktrees for parallel feature work)
git clone --bare git@github.com:IgorCandido/memoria.git ~/Github/thinker/memoria

# Create the main worktree (this is where the code lives)
cd ~/Github/thinker/memoria
git worktree add main main
```

### 2. Provision Storage Backends

Memoria uses **two** stores: Postgres for document records, ChromaDB for vector embeddings. Production deployment runs both on `relishhost1`.

**Postgres (document store)** — table is created on first write; just ensure the `memoria` database exists:

```bash
# On the Postgres host (relishhost1)
createdb -p 5435 memoria
```

**ChromaDB (vector store)** — production hits `relishhost1:8001`. For local dev, run as a Docker container:

```bash
docker run -d \
  --name memoria-chromadb \
  -p 8001:8000 \
  -v ~/Github/thinker/memoria/chroma_data:/data \
  -e CHROMA_SERVER_HOST=0.0.0.0 \
  -e CHROMA_SERVER_HTTP_PORT=8000 \
  -e IS_PERSISTENT=TRUE \
  chromadb/chroma:latest

# Verify
curl http://localhost:8001/api/v1/heartbeat
```

**Ollama (embeddings)** — default adapter posts to `relishhost2:11434`. Pull the model once:

```bash
ollama pull mxbai-embed-large
```

The `chroma_data/` directory at the bare root stores local ChromaDB vector data persistently. It survives container restarts and worktree operations.

**Configure connection** — export the env vars below (or rely on defaults shown):

```bash
export MEMORIA_PG_HOST=relishhost1     MEMORIA_PG_PORT=5435
export MEMORIA_PG_DATABASE=memoria     MEMORIA_PG_USER=postgres
export MEMORIA_PG_PASSWORD=...
export MEMORIA_CHROMA_HOST=relishhost1 MEMORIA_CHROMA_PORT=8001
export MEMORIA_OLLAMA_HOST=relishhost2 MEMORIA_OLLAMA_PORT=11434
```

### 3. Sync Python Dependencies

`uv` manages the venv and installs the `memoria` console script.

```bash
cd ~/Github/thinker/memoria/main
uv sync
uv run memoria health   # smoke-test backends — Postgres, ChromaDB, Ollama
```

### 4. Register as Claude Code Plugin

```bash
cd ~/Github/thinker/memoria/main
./install-plugin.sh
# Adds memoria as a Claude Code plugin (slash command /memoria + SessionStart hook)
```

### 5. Load Documents

Add a document via stdin (the canonical path — content lives in Postgres, not the filesystem):

```bash
cd ~/Github/thinker/memoria/main
cat ~/path/to/doc.md | uv run memoria store "doc.md" - --title "My Doc"
```

Bulk-load a directory of markdown files:

```bash
cd ~/Github/thinker/memoria/main
for f in ~/path/to/docs/*.md; do
  cat "$f" | uv run memoria store "$(basename "$f")" - --title "$(basename "$f" .md)"
done
```

### 6. Test It

```bash
cd ~/Github/thinker/memoria/main
uv run memoria search "how does memoria work"
uv run memoria stats
```

## Repository Structure

This repository uses a **bare root + worktree** layout for safe parallel development:

```
~/Github/thinker/memoria/              (bare git root)
├── HEAD, config, objects/, refs/      (git internals - don't touch)
├── docs/                              (PERSISTENT - RAG source documents)
├── chroma_data/                       (PERSISTENT - ChromaDB vector data)
├── main/                              (worktree: main branch)
│   ├── memoria/                       (Python package - the actual code)
│   │   ├── skill_helpers.py           (PUBLIC API - search, index, stats)
│   │   ├── adapters/                  (ChromaDB, SentenceTransformers, etc.)
│   │   ├── domain/                    (Entities, ports, value objects)
│   │   └── compatibility/             (Legacy raggy facade)
│   ├── tests/                         (Unit, integration, performance tests)
│   ├── specs/                         (Feature specifications)
│   ├── docs -> ../docs                (symlink to persistent docs)
│   ├── chroma_data -> ../chroma_data  (symlink to persistent data)
│   ├── pyproject.toml                 (Package definition)
│   └── README.md                      (this file)
└── <feature-worktrees>/               (temporary, safely deletable)
    ├── docs -> ../docs                (same symlinks)
    └── chroma_data -> ../chroma_data
```

**Why this layout?**
- `docs/` and `chroma_data/` at the bare root are **never affected by worktree operations**
- You can delete any worktree without losing your indexed documents or vector data
- Feature branches get their own worktrees with symlinks to shared data
- ChromaDB Docker container mounts `chroma_data/` at the bare root level

### Creating a Feature Worktree

```bash
cd ~/Github/thinker/memoria
git worktree add 004-configurable-embeddings origin/004-configurable-embeddings

# Set up symlinks in the new worktree
ln -sfn ../docs 004-configurable-embeddings/docs
ln -sfn ../chroma_data 004-configurable-embeddings/chroma_data
```

## How It Works

### Architecture

```
Claude Code → skill_helpers.py / `uv run memoria` CLI → Adapters
                                    │
                                    ├── PostgresDocumentStoreAdapter  (relishhost1:5435/memoria — full document content, versioning)
                                    ├── ChromaDBAdapter               (relishhost1:8001 — vector index)
                                    ├── OllamaEmbeddingAdapter        (relishhost2:11434, mxbai-embed-large, 1024-dim — DEFAULT)
                                    │   └── SentenceTransformerAdapter (all-MiniLM-L6-v2, 384-dim — opt-in via MEMORIA_EMBEDDING_ADAPTER)
                                    ├── SearchEngineAdapter           (hybrid search: 95% semantic + 5% BM25)
                                    └── DocumentProcessorAdapter      (chunking: 2000 chars, 100 overlap)
```

Documents are persisted in Postgres (single source of truth for content) and indexed in ChromaDB (vectors only). Reindex pulls content back from Postgres — the filesystem is no longer load-bearing.

### Search Flow

1. Query text is embedded using SentenceTransformers (`all-MiniLM-L6-v2`, 384 dimensions)
2. ChromaDB performs semantic similarity search
3. BM25 keyword search runs in parallel
4. Results are merged with hybrid scoring (95% semantic, 5% keyword)
5. Top results returned with confidence scores

### Indexing Flow

1. Documents are chunked (2000 chars, 100 char overlap)
2. Chunks are batch-embedded (32 at a time via SentenceTransformers)
3. Embeddings are progressively committed to ChromaDB (every 500 chunks)
4. Failed documents are tracked and reported without blocking the batch

## API Reference

### `search_knowledge(query, mode="hybrid", expand=True, limit=5)`

Search the knowledge base. Returns formatted results with scores.

### `index_documents(pattern="**/*.md", rebuild=False)`

Index documents from `docs/` directory. Uses batch embedding for speed.

### `health_check()`

Check ChromaDB connection and system health.

### `get_stats()`

Get collection statistics (chunk count, database info).

### `list_indexed_documents()`

List all indexed documents organized by directory.

### `add_document(file_path, reindex=True)`

Add a single document to the knowledge base.

## Claude Code Integration

### How Claude Code Uses Memoria

When a Claude Code skill named `memoria` is registered, Claude can invoke it to search your knowledge base. The skill is discovered via the symlink at `~/.claude/skills/memoria`.

### Usage Pattern in Claude Code

```python
# This is how Claude Code invokes memoria internally
import sys
sys.path.insert(0, '/path/to/memoria/main/memoria')
from skill_helpers import search_knowledge

result = search_knowledge(
    query="your search query",
    mode="hybrid",
    expand=True,
    limit=5
)
```

### Debug Logging

Set `MEMORIA_DEBUG=1` to see performance metrics:

```bash
MEMORIA_DEBUG=1 python3 -c "
import sys; sys.path.insert(0, 'memoria')
from skill_helpers import search_knowledge
search_knowledge('test query')
"
# [PERF] semantic_search: embed=15ms, chromadb=8ms
# [PERF] hybrid_search: total=45ms
# [PERF] search_knowledge: query_time=46ms, results=5
```

## Configuration

Backend connections are env-driven. Tuning knobs (chunking, hybrid weights) remain in `memoria/skill_helpers.py`.

| Env var | Default | Purpose |
|---------|---------|---------|
| `MEMORIA_PG_HOST` | `relishhost1` | Postgres host |
| `MEMORIA_PG_PORT` | `5435` | Postgres port |
| `MEMORIA_PG_DATABASE` | `memoria` | Postgres database |
| `MEMORIA_PG_USER` | `postgres` | Postgres user |
| `MEMORIA_PG_PASSWORD` | `` | Postgres password |
| `MEMORIA_CHROMA_HOST` | `relishhost1` | ChromaDB host |
| `MEMORIA_CHROMA_PORT` | `8001` | ChromaDB port |
| `MEMORIA_OLLAMA_HOST` | `relishhost2` | Ollama host |
| `MEMORIA_OLLAMA_PORT` | `11434` | Ollama port |
| `MEMORIA_EMBEDDING_ADAPTER` | `ollama` | `ollama` (mxbai-embed-large, 1024-dim) or `sentence_transformers` (all-MiniLM-L6-v2, 384-dim) |
| `MEMORIA_DEBUG` | unset | Set `1` for perf logging |

Hardcoded tuning (in `memoria/skill_helpers.py`): collection `memoria`, hybrid weight `0.95`, chunk size `2000` / overlap `100`, batch commit `500`, embedding batch `32`.

## Performance

| Metric | Value |
|--------|-------|
| Search latency (mean) | ~25ms |
| Search latency (P99) | ~30ms |
| Results per query | 10 |
| Indexing throughput | >20 docs/min |
| Timeout rate | 0% |
| Memory footprint | ~150-200MB |
| Collection size tested | 18,004 chunks |

## Troubleshooting

### ChromaDB not responding

```bash
docker ps | grep chroma                            # local container running?
curl http://${MEMORIA_CHROMA_HOST:-relishhost1}:${MEMORIA_CHROMA_PORT:-8001}/api/v1/heartbeat
docker restart memoria-chromadb                    # local only
```

### Postgres not reachable

```bash
psql -h "$MEMORIA_PG_HOST" -p "$MEMORIA_PG_PORT" -U "$MEMORIA_PG_USER" -d "$MEMORIA_PG_DATABASE" -c '\dt'
# Should list memoria tables. Errors → check MEMORIA_PG_* env, network, credentials.
```

### Ollama embedding errors

```bash
curl http://${MEMORIA_OLLAMA_HOST:-relishhost2}:${MEMORIA_OLLAMA_PORT:-11434}/api/tags
# Confirm mxbai-embed-large is present. If not: `ollama pull mxbai-embed-large` on that host.
# Fallback to in-process model: export MEMORIA_EMBEDDING_ADAPTER=sentence_transformers
```

### Import errors

```bash
# Reinstall in editable mode
~/path/to/.venv/bin/pip install -e ~/Github/thinker/memoria/main/
```

### Empty search results

```bash
# Check if documents are indexed
python3 -c "
import sys; sys.path.insert(0, 'memoria')
from skill_helpers import get_stats
print(get_stats())
"
# If chunk count is 0, run index_documents()
```

## Specs & Roadmap

| Spec | Status | Description |
|------|--------|-------------|
| 001-chroma-search-fix | Archived | Improved hybrid search confidence (0.54 -> 0.80) |
| 002-memoria-performance | Complete | Batch embedding, progressive indexing, perf logging |
| 003-memoria-plugin-install | Complete | `uv run memoria` CLI + Claude Code plugin install |
| 004-configurable-embeddings | Complete | Ollama embedding adapter, `MEMORIA_EMBEDDING_ADAPTER` switch |
| 005-db-document-storage | Complete | Postgres document store (relishhost1:5435), filesystem decoupled |
| 006-rag-search-quality | In progress | Source dedup, garbage filter, plain text output |

## License

Private repository - Igor Candido
