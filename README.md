# Memoria - RAG Knowledge Base for Claude Code

**Version**: 3.1.0
**Status**: Production Ready
**Architecture**: Onion Architecture with Domain-Driven Design

Memoria is a lightweight RAG (Retrieval-Augmented Generation) skill that gives Claude Code persistent memory through semantic search over your documents. It replaces heavy MCP server stacks with direct Python execution - 98.7% fewer tokens, 75% less memory.

> **TODO**: An automated installer is planned for the next feature (spec 003). For now, follow the manual setup below.

## Quick Start

### Prerequisites

- **macOS** (tested on macOS 15+)
- **Python 3.11+** (`python3 --version`)
- **Docker** via Colima or Docker Desktop (for ChromaDB)
- **Claude Code** installed (`claude --version`)

### 1. Clone the Repository

```bash
# Clone as bare repo (supports git worktrees for parallel feature work)
git clone --bare git@github.com:IgorCandido/memoria.git ~/Github/thinker/memoria

# Create the main worktree (this is where the code lives)
cd ~/Github/thinker/memoria
git worktree add main main
```

### 2. Start ChromaDB

ChromaDB is the vector database that stores embeddings. It runs as a Docker container.

```bash
# Start ChromaDB container
docker run -d \
  --name memoria-chromadb \
  -p 8001:8000 \
  -v ~/Github/thinker/memoria/chroma_data:/data \
  -e CHROMA_SERVER_HOST=0.0.0.0 \
  -e CHROMA_SERVER_HTTP_PORT=8000 \
  -e IS_PERSISTENT=TRUE \
  chromadb/chroma:latest

# Verify it's running
curl http://localhost:8001/api/v1/heartbeat
# Should return: {"nanosecond heartbeat": ...}
```

The `chroma_data/` directory at the bare root stores all vector data persistently. It survives container restarts and worktree operations.

### 3. Install Python Dependencies

```bash
# Create a virtual environment (or use an existing shared one)
python3 -m venv ~/Github/thinker/memoria/main/.venv

# Install memoria in editable mode
~/Github/thinker/memoria/main/.venv/bin/pip install -e ~/Github/thinker/memoria/main/

# Verify
~/Github/thinker/memoria/main/.venv/bin/python3 -c "import memoria; print('OK:', memoria.__file__)"
```

### 4. Register as Claude Code Skill

```bash
# Create the skill symlink (Claude Code discovers skills from ~/.claude/skills/)
mkdir -p ~/.claude/skills
ln -sfn ~/Github/thinker/memoria/main ~/.claude/skills/memoria
```

### 5. Set Up Document Directory

```bash
# Create persistent docs directory at bare root (not inside a worktree)
mkdir -p ~/Github/thinker/memoria/docs

# Create symlink from worktree to bare root docs
ln -sfn ../docs ~/Github/thinker/memoria/main/docs

# Add your markdown documents
cp ~/path/to/your/docs/*.md ~/Github/thinker/memoria/docs/
```

### 6. Index Your Documents

```bash
# Index all markdown files in the docs/ directory
~/Github/thinker/memoria/main/.venv/bin/python3 << 'EOF'
import sys, os
sys.path.insert(0, os.path.expanduser('~/Github/thinker/memoria/main/memoria'))
from skill_helpers import index_documents
os.chdir(os.path.expanduser('~/Github/thinker/memoria/docs'))
print(index_documents(pattern="**/*.md"))
EOF
```

### 7. Test It

```bash
~/Github/thinker/memoria/main/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, os.path.expanduser('~/Github/thinker/memoria/main/memoria'))
from skill_helpers import search_knowledge
print(search_knowledge(query="how does memoria work", mode="hybrid", limit=5))
EOF
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
Claude Code → skill_helpers.py → Adapters → ChromaDB (Docker, port 8001)
                                    │
                                    ├── ChromaDBAdapter (vector store)
                                    ├── SentenceTransformerAdapter (embeddings: all-MiniLM-L6-v2)
                                    ├── SearchEngineAdapter (hybrid search: 95% semantic + 5% BM25)
                                    └── DocumentProcessorAdapter (chunking: 2000 chars, 100 overlap)
```

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

All configuration is currently hardcoded in `memoria/skill_helpers.py`. Planned: env var overrides (spec 004).

| Setting | Value | Location |
|---------|-------|----------|
| ChromaDB host | `localhost` | `skill_helpers.py:76` |
| ChromaDB port | `8001` | `skill_helpers.py:77` |
| Collection name | `"memoria"` | `skill_helpers.py:74` |
| Embedding model | `all-MiniLM-L6-v2` | `skill_helpers.py:80` |
| Hybrid weight | `0.95` (95% semantic) | `skill_helpers.py:81` |
| Chunk size | `2000` chars | `skill_helpers.py:82` |
| Chunk overlap | `100` chars | `skill_helpers.py:82` |
| Batch commit size | `500` chunks | `skill_helpers.py:142` |
| Embedding batch | `32` texts | SentenceTransformer native |

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
# Check container is running
docker ps | grep chroma

# Check port is available
curl http://localhost:8001/api/v1/heartbeat

# Restart container
docker restart memoria-chromadb
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
| 003-memoria-plugin-install | Planned | Automated curl installer for one-command setup |
| 004-configurable-embeddings | Future | Configurable embedding models via Ollama (fix score range) |

## License

Private repository - Igor Candido
