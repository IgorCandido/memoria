# Memoria v3.0.0 - Deployment Quick Start Guide

**For**: Team Developers
**Version**: 3.0.0
**Date**: 2025-11-30

---

## TL;DR - What You Need to Know

Memoria is a **RAG (semantic search) skill** for Claude Code that:
- Searches your documentation using AI embeddings
- Replaces the old MCP architecture with 98.7% lower token usage
- Works directly via Python (no Docker containers for memoria itself)
- Requires ChromaDB running on port 8001

**Status**: ✅ Production Ready (main branch)

---

## Prerequisites

Before deployment, ensure:

1. **Python 3.11+** installed
2. **ChromaDB Docker container** running on port 8001
3. **~500MB disk space** for embedding model
4. **~150MB RAM** for skill runtime

---

## Quick Setup (5 Minutes)

### 1. Create Shared Virtual Environment (if not exists)

```bash
cd ~/Github/thinker/claude_infra/skills
python3 -m venv .venv
```

### 2. Install Memoria Dependencies

```bash
cd ~/Github/thinker/claude_infra/skills/memoria

# Use shared venv with absolute path
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/pip install -e .

# Optional: Install dev dependencies (for testing)
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/pip install -e ".[dev]"
```

### 3. Verify Installation

```bash
# Test health check (use ABSOLUTE paths!)
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import health_check
print(health_check())
EOF
```

**Expected Output**:
```
🏥 Health Check

 RAG System  ✅ Healthy
 ChromaDB    ✅ Connected (XXXX chunks)
 Docs        ✅ XX files
```

### 4. Test Search

```bash
# Test search functionality
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import search_knowledge
print(search_knowledge(query="memoria architecture", limit=3))
EOF
```

---

## Usage from Claude Code

### Basic Pattern

```python
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import search_knowledge

# Search knowledge base
results = search_knowledge(
    query="your search query",
    mode="hybrid",  # semantic + BM25 (recommended)
    expand=True,    # query expansion
    limit=5
)
print(results)
```

### Available Functions

| Function | Purpose | Example |
|----------|---------|---------|
| `health_check()` | System status | `health_check()` |
| `search_knowledge(query, ...)` | Semantic search | `search_knowledge("chronos", limit=5)` |
| `get_stats()` | Database stats | `get_stats()` |
| `list_indexed_documents()` | List docs | `list_indexed_documents()` |
| `index_documents(pattern)` | Index files | `index_documents("**/*.md")` |
| `add_document(path)` | Add single doc | `add_document("/path/to/doc.md")` |

---

## Common Issues & Fixes

### Issue: ChromaDB Not Connected

**Symptom**: `health_check()` shows ChromaDB not connected

**Fix**:
```bash
# Check if ChromaDB is running
docker ps | grep chroma

# If not running, start it
docker start memoria-chromadb

# Test connection
curl http://localhost:8001/api/v2/heartbeat
```

### Issue: ModuleNotFoundError

**Symptom**: `ModuleNotFoundError: No module named 'skill_helpers'`

**Fix**:
```bash
# Ensure you're in the right directory
cd ~/Github/thinker/claude_infra/skills/memoria

# Reinstall using shared venv
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/pip install -e .

# Use correct sys.path in your code (absolute path required)
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
```

### Issue: Slow Search

**Symptom**: Search takes > 5 seconds

**Fix**:
```python
# Reduce limit
search_knowledge(query="...", limit=3)  # Instead of 10

# Disable query expansion
search_knowledge(query="...", expand=False)

# Use semantic-only mode
search_knowledge(query="...", mode="semantic")
```

---

## Testing (Optional)

### Run Core Tests

```bash
# Use shared venv with absolute paths (works from any directory)
cd ~/Github/thinker/claude_infra/skills/memoria
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/pytest tests/domain tests/adapters tests/ports -v

# Run with coverage
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/pytest tests/domain tests/adapters tests/ports -v --cov=memoria
```

**Expected Result**: 129/129 tests passing

### Test Coverage

| Component | Coverage | Status |
|-----------|----------|--------|
| Domain entities | 100% | ✅ |
| Adapters | 89-98% | ✅ |
| Ports | 60-70% | ✅ |
| Overall (core) | 63% | ✅ |

---

## Architecture Overview (For Reference)

### Onion Architecture

```
┌─────────────────────────────────────────────────────┐
│              skill_helpers.py (API)                  │
├─────────────────────────────────────────────────────┤
│                  Adapters Layer                      │
│  • ChromaDB (vector storage)                         │
│  • SentenceTransformers (embeddings)                 │
│  • DocumentProcessor (chunking)                      │
│  • SearchEngine (semantic + BM25)                    │
├─────────────────────────────────────────────────────┤
│                  Domain Layer                        │
│  • Entities: Document, Chunk, SearchResult           │
│  • Value Objects: Embedding, QueryTerms              │
│  • Ports: Clean interfaces                           │
└─────────────────────────────────────────────────────┘
```

### Key Principles

- **Immutable entities**: Frozen dataclasses, no side effects
- **Port/Adapter pattern**: Clean separation of concerns
- **Dependency inversion**: Domain has zero external dependencies
- **Type safety**: mypy strict mode compliance

---

## Performance Comparison

### vs. MCP Architecture (v2.0)

| Metric | MCP v2.0 | Skill v3.0 | Improvement |
|--------|----------|------------|-------------|
| Token Usage | ~150,000 | ~2,000 | 98.7% ↓ |
| Memory | ~700MB | ~150MB | 78% ↓ |
| Startup | ~5-10s | <1s | 90% ↓ |
| Layers | 6 | 2 | 67% ↓ |

---

## Documentation Resources

### Essential Reading

- **README.md**: Full architecture and API reference (530 lines)
- **SKILL_USAGE.md**: Usage patterns and examples (860 lines)
- **DEPLOYMENT_READINESS.md**: Production validation report
- **RELEASE_NOTES.md**: Version history

### Quick Links

- **Main API**: `memoria/skill_helpers.py` (high-level functions)
- **Domain Entities**: `memoria/domain/entities.py`
- **ChromaDB Adapter**: `memoria/adapters/chromadb/chromadb_adapter.py`

---

## Support & Troubleshooting

### Health Check Command

```bash
# Use absolute paths (works from any directory)
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 -c "import sys; sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria'); from skill_helpers import health_check; print(health_check())"
```

### Check ChromaDB Status

```bash
# Container status
docker ps | grep chroma

# API health
curl http://localhost:8001/api/v2/heartbeat

# Collection info
curl http://localhost:8001/api/v2/collections
```

### Run Quick Test

```bash
# Use shared venv with absolute path
cd ~/Github/thinker/claude_infra/skills/memoria
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/pytest tests/domain/test_entities.py -v
```

---

## Deployment Checklist

### Before Deploying to Your Machine

- [ ] Python 3.11+ installed
- [ ] ChromaDB container running (port 8001)
- [ ] ~500MB free disk space
- [ ] ~150MB free RAM

### After Installation

- [ ] Run `health_check()` - should show ✅ Healthy
- [ ] Run `search_knowledge("test", limit=1)` - should return results
- [ ] Run core tests (optional) - should pass 129/129

### If Issues Occur

1. Check ChromaDB is running: `docker ps | grep chroma`
2. Verify shared venv installed: `ls ~/Github/thinker/claude_infra/skills/.venv/bin/python3`
3. Test imports: `/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 -c "import chromadb, sentence_transformers"`
4. Read DEPLOYMENT_READINESS.md for detailed troubleshooting

---

## What NOT to Do

❌ **Don't** modify the v3.x branch (it's for future dual-storage work)
❌ **Don't** use the old MCP server (deprecated)
❌ **Don't** run memoria without ChromaDB (it will fail)
❌ **Don't** use bare `python3` - always use venv python
❌ **Don't** skip virtual environment creation

---

## Quick Reference Card

### Installation
```bash
# Create shared venv (if not exists)
cd ~/Github/thinker/claude_infra/skills
python3 -m venv .venv

# Install memoria into shared venv
cd ~/Github/thinker/claude_infra/skills/memoria
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/pip install -e .
```

### Usage
```python
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import search_knowledge
search_knowledge("query", mode="hybrid", limit=5)
```

### Health Check
```bash
curl http://localhost:8001/api/v2/heartbeat
```

### Testing
```bash
cd ~/Github/thinker/claude_infra/skills/memoria
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/pytest tests/domain tests/adapters tests/ports -v
```

---

## FAQ

### Q: Do I need Docker for memoria?

**A**: You need ChromaDB in Docker (port 8001), but memoria itself runs as a Python package. No Docker container for memoria.

### Q: What happened to the MCP server?

**A**: Deprecated. Skills are the new architecture (98.7% token reduction, much simpler).

### Q: Can I use both MCP and skill?

**A**: Yes, but skill is recommended. They use the same ChromaDB backend, so data is compatible.

### Q: What is the v3.x branch?

**A**: Future work for dual-storage (Postgres + ChromaDB). Not for deployment yet. Use main branch (v3.0.0).

### Q: How do I update memoria?

**A**: `git pull` in the memoria directory, then use shared venv: `/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/pip install -e .` to reinstall.

### Q: Where are the docs stored?

**A**: In the `docs/` directory. Index them with `index_documents("**/*.md")`.

---

## Next Steps After Installation

1. **Test basic functionality** with `health_check()` and `search_knowledge()`
2. **Read SKILL_USAGE.md** for detailed usage patterns
3. **Index your documents** if needed with `index_documents()`
4. **Integrate into your workflow** using the Python API

---

## Contact & Issues

- **Repository**: `/Users/igorcandido/Github/thinker/claude_infra/skills/memoria`
- **Branch**: main (v3.0.0)
- **Issues**: Document in your team's issue tracker
- **Questions**: Refer to README.md and SKILL_USAGE.md first

---

**Last Updated**: 2025-11-30
**Version**: 3.0.0
**Status**: ✅ Production Ready
**Deployment Time**: ~5 minutes

---

## Visual Guide

### Success Indicators

✅ **Health check passes**
```
🏥 Health Check
 RAG System  ✅ Healthy
 ChromaDB    ✅ Connected (58437 chunks)
 Docs        ✅ 23 files
```

✅ **Search returns results**
```
📚 Search Results for "test"
Result 1 (Score: 0.85)
Source: example.md
...
```

✅ **Tests pass**
```
===== 129 passed in 19.16s =====
```

### Failure Indicators

❌ **ChromaDB not connected**
```
 ChromaDB    ❌ Not connected
```
**Fix**: Start ChromaDB container

❌ **ModuleNotFoundError**
```
ModuleNotFoundError: No module named 'skill_helpers'
```
**Fix**: Check sys.path, reinstall with pip

❌ **No results found**
```
No results found for "query"
```
**Fix**: Index documents first with `index_documents()`

---

**End of Quick Start Guide**
