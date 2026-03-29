---
description: RAG knowledge base backed by PostgreSQL and ChromaDB. Use for searching prior knowledge, storing documents, and corpus management.
---

# Memoria Skill: RAG Knowledge Base

## Overview

Memoria is a RAG (Retrieval-Augmented Generation) knowledge base backed by PostgreSQL (document store) and ChromaDB (vector store) with Ollama embeddings. All infrastructure runs on relishhost1/relishhost2.

## When to Use

Use memoria for any non-trivial request that benefits from retrieving prior knowledge, documented patterns, or stored context.

## Quick Start

All commands run via `uv` from the memoria project directory:

```bash
MEMORIA="/Users/igorcandido/Github/thinker/memoria/main"

# Search
cd $MEMORIA && uv run memoria search "your query"
cd $MEMORIA && uv run memoria search "your query" --mode semantic --limit 10

# Store
cd $MEMORIA && uv run memoria store "source-id.md" "content here" --title "Title"

# Store large content via stdin
cat file.md | (cd $MEMORIA && uv run memoria store "source-id.md" - --title "Title")

# Retrieve
cd $MEMORIA && uv run memoria get "source-id.md"

# Delete
cd $MEMORIA && uv run memoria delete "source-id.md"

# List all documents
cd $MEMORIA && uv run memoria list

# Health check
cd $MEMORIA && uv run memoria health

# Stats
cd $MEMORIA && uv run memoria stats
```

## API Reference

| Command | Purpose |
|---------|---------|
| `memoria search <query>` | Hybrid RAG search (--mode hybrid/semantic/keyword, --limit N) |
| `memoria store <id> <content>` | Store + embed a document (use `-` for stdin, --title) |
| `memoria get <id>` | Retrieve full document content |
| `memoria delete <id>` | Delete from Postgres + remove ChromaDB chunks |
| `memoria list` | List all active documents |
| `memoria health` | Health check (ChromaDB, Postgres) |
| `memoria stats` | Show collection stats |
| `memoria export <path>` | Export all docs to JSONL |
| `memoria import <path>` | Import docs from JSONL |
| `memoria reindex` | Re-embed all docs with atomic ChromaDB swap |

## Infrastructure

- **PostgreSQL**: relishhost1 (192.168.1.153:5435), db=memoria
- **ChromaDB**: relishhost1 (192.168.1.153:8001), collection=memoria
- **Ollama**: relishhost2 (192.168.1.171:11434), model=mxbai-embed-large

Config loaded from `~/.claude/memoria.env`.
