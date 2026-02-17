---
name: memoria
description: RAG knowledge base search and document management. Query indexed documents with hybrid semantic+keyword search. Use for retrieving stored knowledge, checking what's indexed, and managing the document corpus.
---

# memoria

RAG (Retrieval-Augmented Generation) knowledge base powered by ChromaDB and sentence-transformers. Provides hybrid search (95% semantic, 5% BM25 keyword) across ~293 indexed documents (~17K chunks).

## When to Use

Use this skill when:
- You need to search stored knowledge (docs, specs, architecture decisions, troubleshooting guides)
- You need to check what documents are indexed
- You need to add or index new documents
- You need system health/stats information

## How to Invoke

```python
import sys
sys.path.insert(0, '/Users/igorcandido/.claude/skills/memoria/memoria')
from skill_helpers import search_knowledge

# Search for knowledge
results = search_knowledge(
    query="your search query here",
    mode="hybrid",   # "hybrid" (recommended) or "semantic"
    expand=True,     # automatic query expansion
    limit=5          # number of results
)
print(results)
```

**IMPORTANT**: You must use the shared venv Python to execute this:

```bash
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'PYEOF'
import sys
sys.path.insert(0, '/Users/igorcandido/.claude/skills/memoria/memoria')
from skill_helpers import search_knowledge
results = search_knowledge(query="your query", mode="hybrid", expand=True, limit=5)
print(results)
PYEOF
```

## Available Functions

| Function | Description |
|----------|-------------|
| `search_knowledge(query, mode, expand, limit)` | Search indexed documents |
| `index_documents(pattern, rebuild)` | Bulk index docs from docs/ folder |
| `add_document(file_path, reindex)` | Add and index a single document |
| `list_indexed_documents()` | List all indexed documents |
| `get_stats()` | Show ChromaDB statistics |
| `health_check()` | Verify system health |
| `check_unindexed_documents(pattern)` | Find docs not yet indexed |
| `auto_index_new_documents(pattern)` | Index only new/unindexed docs |

## Common Mistakes

- **DO NOT** use bare `python3` — use the shared venv path: `/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3`
- **DO NOT** try `from skill_helpers import store_knowledge` — the function is `search_knowledge`
- **DO NOT** look for `.venv` in `memoria/main/` — the venv is at `claude_infra/skills/.venv/`
- **DO NOT** try `import memoria` with system Python — use the shared venv or the `sys.path.insert` pattern above

## Infrastructure

- **ChromaDB**: localhost:8001 (Docker container `memoria-chromadb`)
- **Embedding model**: all-MiniLM-L6-v2 (384 dimensions)
- **Collection**: "memoria"
