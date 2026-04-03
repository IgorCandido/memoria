# Memoria - RAG Knowledge Base

## What Is This

Memoria is a **Retrieval-Augmented Generation (RAG)** system that stores documents in PostgreSQL, chunks and embeds them via Ollama, and indexes the embeddings in ChromaDB for hybrid search. It exposes a CLI (`memoria`) and a Python API (`skill_helpers.py`), and ships as a **Claude Code plugin** for automatic RAG priming in conversations.

**Version**: 3.0.0 | **Python**: >=3.11 | **Package manager**: uv

## Architecture

Onion architecture with ports and adapters:

```
memoria/
  domain/
    entities.py          # Document, SearchResult, Chunk, StoredDocument, ImportResult, ReindexResult
    value_objects.py     # Embedding
    errors.py            # Domain exceptions
    ports/               # Protocol interfaces (DocumentStorePort, EmbeddingGeneratorPort, VectorStorePort, etc.)
    services/            # Domain services
  adapters/
    postgres/            # PostgresDocumentStoreAdapter  (document store, single source of truth)
    chromadb/            # ChromaDBAdapter               (vector store for chunk embeddings)
    ollama/              # OllamaEmbeddingAdapter         (mxbai-embed-large, 1024 dims)
    sentence_transformers/ # SentenceTransformerAdapter   (alternative local embedder)
    document/            # DocumentProcessorAdapter       (chunking)
    search/              # SearchEngineAdapter            (hybrid search: semantic + keyword)
    stubs/               # In-memory stubs for unit tests
  application/
    use_cases/           # SearchKnowledge use case
  compatibility/         # Legacy raggy.py facade
  cli.py                 # CLI entry point (argparse)
  skill_helpers.py       # High-level API used by CLI and plugin
```

**Data flow**: Content -> PostgreSQL (full doc, versioned, fingerprinted) -> chunk -> Ollama embed -> ChromaDB (chunks + vectors)

## Infrastructure Requirements

Three services must be running:

| Service    | Default Host       | Port  | Purpose                    |
|------------|--------------------|-------|----------------------------|
| PostgreSQL | 192.168.1.153      | 5435  | Document store (db=memoria, user=postgres) |
| ChromaDB   | 192.168.1.153      | 8001  | Vector store (collection=memoria, v2 API)  |
| Ollama     | 192.168.1.171      | 11434 | Embeddings (model=mxbai-embed-large)       |

Connection config is read from env vars (`MEMORIA_PG_HOST`, `MEMORIA_PG_PORT`, etc.) which are loaded from `~/.claude/memoria.env` at import time.

## Setup

### 1. Clone and install dependencies

```bash
git clone git@github.com:IgorCandido/memoria.git
cd memoria
# The code lives in the `main` worktree (bare repo layout)
cd main
uv sync          # creates .venv and installs all deps
uv sync --dev    # include dev deps (pytest, ruff, mypy, etc.)
```

### 2. Configure environment

Create `~/.claude/memoria.env` (or run `bash install-plugin.sh` which prompts interactively):

```env
MEMORIA_PG_HOST=192.168.1.153
MEMORIA_PG_PORT=5435
MEMORIA_PG_DATABASE=memoria
MEMORIA_PG_USER=postgres
MEMORIA_PG_PASSWORD=<your-password>
MEMORIA_CHROMA_HOST=192.168.1.153
MEMORIA_CHROMA_PORT=8001
MEMORIA_OLLAMA_HOST=192.168.1.171
MEMORIA_OLLAMA_PORT=11434
MEMORIA_EMBEDDING_ADAPTER=ollama
```

PostgreSQL password is stored in Vault at `http://192.168.1.153:8200` (retrieved via 1Password "Vault Root Token - relishhost1" from LocalLab vault).

### 3. Verify infrastructure

```bash
uv run memoria health    # checks ChromaDB + Postgres connectivity
uv run memoria stats     # shows chunk count and collection info
```

### 4. Install as Claude Code plugin (optional)

```bash
bash install-plugin.sh
```

This registers the plugin marketplace, installs the `memoria` skill and `SessionStart` hook that primes every conversation with RAG awareness.

## CLI Reference

All commands are run from the project root via `uv run memoria <command>`:

| Command | Description |
|---------|-------------|
| `search <query> [--mode hybrid\|semantic\|keyword] [--limit N]` | Search the knowledge base |
| `store <source_id> <content\|-> [--title T]` | Store a document (use `-` for stdin) |
| `get <source_id>` | Retrieve full document content |
| `delete <source_id>` | Soft-delete from Postgres + remove ChromaDB chunks |
| `list` | List all active documents |
| `health` | Health check |
| `stats` | Show collection stats |
| `export <path>` | Export all docs to JSONL |
| `import <path>` | Import docs from JSONL (idempotent by fingerprint) |
| `reindex` | Re-embed all docs with atomic ChromaDB collection swap |

## Testing

```bash
# Unit tests only (no infra needed)
uv run pytest tests/unit/ -v

# All tests except integration
uv run pytest -v

# Integration tests (requires running Postgres, ChromaDB, Ollama)
uv run pytest --run-integration tests/integration/ -v

# Full suite with coverage
uv run pytest --run-integration -v
```

Coverage threshold: 70% (enforced by pytest config in `pyproject.toml`).

Test markers: `unit`, `integration`, `slow`.

## Key Design Decisions

- **PostgreSQL is the source of truth** for documents. ChromaDB stores only derived chunks/embeddings and can be rebuilt from Postgres via `reindex`.
- **Soft-delete**: Documents are deactivated, not removed, to support reactivation.
- **Fingerprint-based idempotency**: SHA-256 of stripped content. Store/import skip unchanged documents.
- **Atomic reindex**: Writes to a temp ChromaDB collection first, then swaps on success. Original preserved on failure.
- **Hybrid search** with 0.95 weight toward semantic (Ollama embeddings) blended with keyword matching.
- **Source dedup + garbage filtering** in search results to avoid returning multiple low-quality chunks from the same source.

## Plugin Structure

```
memoria-plugin/
  .claude-plugin/plugin.json    # Plugin metadata (name, version)
  hooks/
    hooks.json                  # SessionStart hook registration
    sessionstart_wrapper.sh     # Shell wrapper
    sessionstart.py             # Injects RAG usage instructions into conversation
  skills/
    memoria/SKILL.md            # Skill description and API reference for Claude
```

## Common Tasks

### Store knowledge during a session
```bash
uv run memoria store "topic-name.md" "document content" --title "Descriptive Title"
# Or pipe large content:
cat somefile.md | uv run memoria store "topic-name.md" - --title "Title"
```

### Rebuild all embeddings (e.g. after model change)
```bash
uv run memoria reindex
```

### Export/import for backup or migration
```bash
uv run memoria export /tmp/backup.jsonl
uv run memoria import /tmp/backup.jsonl
```

## Code Quality

- **Linter**: `uv run ruff check .`
- **Formatter**: `uv run black .`
- **Type checker**: `uv run mypy memoria/` (strict mode)
- **Import sorting**: `uv run isort .`
