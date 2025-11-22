# Memoria Skill - Usage Guide

**Version**: 3.0.0
**Target Audience**: Claude Code users and Python developers

**⚠️ IMPORTANT**: All code examples in this guide show only the Python code for clarity. **You MUST wrap them in the bash invocation with shared venv python**. See the Quick Start section below for the complete pattern, or read `QUICK-START-INVOCATION.md` for copy-paste examples.

This guide provides practical examples and patterns for using the memoria skill effectively.

## Table of Contents

- [Quick Start](#quick-start)
- [Common Workflows](#common-workflows)
- [Search Patterns](#search-patterns)
- [Document Management](#document-management)
- [Integration Patterns](#integration-patterns)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Quick Start

### ⚠️ CRITICAL: Use Shared Venv Python

**All examples MUST use the shared venv python path:**
```bash
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3
```

**DO NOT use bare `python3` - it will fail with ModuleNotFoundError!**

### 1. Basic Health Check

```bash
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import health_check

# Check if RAG system is healthy
print(health_check())
EOF
```

**Output**:
```
🏥 Health Check

RAG System  ✅ Healthy
ChromaDB    ✅ Connected (54314 chunks)
Docs        ✅ 3 files
```

### 2. Basic Search

```bash
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import search_knowledge

# Search for information
results = search_knowledge(
    query="chronos scheduling",
    mode="hybrid",
    limit=3
)
print(results)
EOF
```

**Output**:
```
📚 Search Results for "chronos scheduling"

Result 1 (Score: 0.46)
Source: claude-infrastructure-chronos.md
┌────────────────────────────────────────────┐
│ Chronos is a production-grade task         │
│ scheduling system with MCP interface...    │
└────────────────────────────────────────────┘
```

## Common Workflows

### Workflow 1: Initial Setup

**When**: First time using memoria or after adding new documents

```bash
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import health_check, index_documents, get_stats

# 1. Check system health
print(health_check())

# 2. Index all markdown documents
print(index_documents(pattern="**/*.md"))

# 3. Verify indexing
print(get_stats())
EOF
```

**Expected Output**:
```
✅ Indexing Complete

Documents: 15
Chunks: 1,234

📊 Stats

Chunks      55,548
Database    ChromaDB (HTTP)
Collection  memoria
```

### Workflow 2: Research / Discovery

**When**: Exploring unfamiliar codebase or finding documentation

```bash
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import search_knowledge

# Step 1: Broad search to understand domain
results = search_knowledge(
    query="what is chronos",
    mode="hybrid",
    expand=True,
    limit=5
)
print(results)

# Step 2: Narrow down to specific feature
results = search_knowledge(
    query="chronos task scheduling implementation",
    mode="hybrid",
    limit=3
)
print(results)

# Step 3: Find configuration examples
results = search_knowledge(
    query="chronos redis configuration",
    mode="hybrid",
    limit=3
)
print(results)
EOF
```

### Workflow 3: Adding New Documentation

**When**: You create new documentation and want it searchable

```bash
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import add_document, get_stats

# Before adding
print("Before:", get_stats())

# Add new document
result = add_document(
    file_path="/path/to/new-feature-docs.md",
    reindex=True
)
print(result)

# After adding
print("After:", get_stats())
EOF
```

**Output**:
```
Before: Chunks: 54,314

✅ Added: new-feature-docs.md
🔄 Re-indexing...
✅ Done

After: Chunks: 54,489
```

### Workflow 4: Periodic Maintenance

**When**: Monthly or after significant documentation changes

```python
from skill_helpers import list_indexed_documents, index_documents, get_stats

# 1. List current documents
print(list_indexed_documents())

# 2. Re-index everything (rebuild=False only indexes new/changed)
print(index_documents(pattern="**/*.md", rebuild=False))

# 3. Check stats
print(get_stats())
```

## Search Patterns

### Pattern 1: Question Answering

**Use Case**: Finding specific answers to questions

```python
from skill_helpers import search_knowledge

# Direct questions
questions = [
    "how does memoria handle embeddings?",
    "what is the chronos scheduling frequency?",
    "where is Redis configuration stored?",
    "why was onion architecture chosen?"
]

for question in questions:
    print(f"\nQ: {question}")
    results = search_knowledge(query=question, mode="hybrid", limit=1)
    print(results)
```

**Best Practices**:
- Use natural language questions
- Enable query expansion (`expand=True`)
- Use hybrid mode for best results
- Limit=1 for quick answers, limit=5 for context

### Pattern 2: Concept Exploration

**Use Case**: Understanding broad topics or architectures

```python
from skill_helpers import search_knowledge

# Broad concept search
concepts = [
    "onion architecture",
    "domain driven design",
    "adapter pattern"
]

for concept in concepts:
    print(f"\n📖 Exploring: {concept}")
    results = search_knowledge(
        query=concept,
        mode="hybrid",
        expand=True,
        limit=5  # More results for comprehensive understanding
    )
    print(results)
```

**Best Practices**:
- Use fewer keywords (2-3 words max)
- Enable query expansion
- Request more results (5-10)
- Use hybrid mode for relevance

### Pattern 3: Code Search

**Use Case**: Finding specific code patterns or implementations

```python
from skill_helpers import search_knowledge

# Code-specific searches
code_queries = [
    "Document entity implementation",
    "ChromaDBAdapter connection code",
    "embedding generation function",
    "search engine hybrid algorithm"
]

for query in code_queries:
    print(f"\n🔍 Searching: {query}")
    results = search_knowledge(
        query=query,
        mode="hybrid",
        limit=3
    )
    print(results)
```

**Best Practices**:
- Include function/class names if known
- Use technical terminology
- Hybrid mode works well for code
- Check multiple results for context

### Pattern 4: Troubleshooting Search

**Use Case**: Finding error solutions or debugging info

```python
from skill_helpers import search_knowledge

# Error message or symptom
error_query = "FrozenInstanceError cannot assign"

print(f"🔧 Troubleshooting: {error_query}")
results = search_knowledge(
    query=error_query,
    mode="hybrid",  # Hybrid catches exact error strings
    limit=5
)
print(results)

# Related troubleshooting
followup = "frozen dataclass immutable entities"
print(f"\n🔧 Related: {followup}")
results = search_knowledge(query=followup, mode="semantic", limit=3)
print(results)
```

**Best Practices**:
- Use exact error messages first (hybrid mode)
- Then use semantic mode for concepts
- Check 5-10 results for solutions
- Follow up with related concepts

## Document Management

### Adding Single Documents

```python
from skill_helpers import add_document

# Add with auto-reindexing
add_document("/path/to/doc.md", reindex=True)

# Add without reindexing (faster, but search won't find it yet)
add_document("/path/to/doc.md", reindex=False)
```

**When to Reindex**:
- ✅ Adding 1-3 documents: `reindex=True`
- ❌ Batch adding many documents: `reindex=False`, then `index_documents()` once

### Bulk Indexing

```python
from skill_helpers import index_documents
import shutil
from pathlib import Path

# Copy multiple documents
docs_to_add = [
    "/source/doc1.md",
    "/source/doc2.md",
    "/source/doc3.md"
]

docs_dir = Path("/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/docs")

for doc in docs_to_add:
    dest = docs_dir / Path(doc).name
    shutil.copy2(doc, dest)
    print(f"Copied: {dest.name}")

# Now index everything at once
print("\nIndexing all documents...")
print(index_documents(pattern="**/*.md"))
```

### Listing Documents

```python
from skill_helpers import list_indexed_documents

# Get organized list
docs = list_indexed_documents()
print(docs)
```

**Output**:
```
📄 Documents (15 files)

root/
  - CLAUDE.md
  - README.md

chronos/
  - chronos-architecture.md
  - chronos-api.md

memoria/
  - memoria-guide.md
  - memoria-phase2.md
```

### Checking Statistics

```python
from skill_helpers import get_stats

stats = get_stats()
print(stats)
```

**Output**:
```
📊 Stats

Chunks      54,314
Database    ChromaDB (HTTP)
Collection  memoria
```

## Integration Patterns

### Pattern 1: Claude Code Loop Machine

**Use Case**: RAG-driven workflow in Claude Code sessions

```python
from skill_helpers import search_knowledge

# Step 1: User asks question
user_query = "How do I schedule a task with chronos?"

# Step 2: Query RAG
rag_results = search_knowledge(
    query=user_query,
    mode="hybrid",
    expand=True,
    limit=5
)

# Step 3: Use results to inform response
print(rag_results)
# ... Claude processes results and responds to user
```

### Pattern 2: Documentation Generator

**Use Case**: Generate documentation from RAG knowledge

```python
from skill_helpers import search_knowledge

topic = "memoria architecture"

# Gather information
architecture_info = search_knowledge(query=f"{topic} overview", limit=5)
components_info = search_knowledge(query=f"{topic} components", limit=5)
usage_info = search_knowledge(query=f"{topic} usage", limit=3)

# Combine results into structured documentation
doc = f"""
# {topic.title()}

## Overview
{architecture_info}

## Components
{components_info}

## Usage
{usage_info}
"""

print(doc)
```

### Pattern 3: Automated Q&A System

**Use Case**: Answer common questions automatically

```python
from skill_helpers import search_knowledge

faq = [
    "What is memoria?",
    "How do I install memoria?",
    "What is the difference between semantic and hybrid search?",
    "How do I add documents to memoria?"
]

print("# Frequently Asked Questions\n")

for question in faq:
    print(f"## {question}\n")
    answer = search_knowledge(query=question, mode="hybrid", limit=1)
    print(answer)
    print()
```

### Pattern 4: Code Review Assistant

**Use Case**: Find related code or patterns during review

```python
from skill_helpers import search_knowledge

# Reviewer sees code pattern and wants context
code_pattern = "frozen dataclass pattern"

# Find documentation
docs = search_knowledge(
    query=f"{code_pattern} documentation",
    mode="hybrid",
    limit=3
)

# Find examples
examples = search_knowledge(
    query=f"{code_pattern} examples",
    mode="hybrid",
    limit=3
)

# Find rationale
rationale = search_knowledge(
    query=f"why use {code_pattern}",
    mode="semantic",  # Semantic for "why" questions
    limit=2
)

print("Documentation:", docs)
print("\nExamples:", examples)
print("\nRationale:", rationale)
```

## Troubleshooting

### Issue: No Results Found

**Symptom**: `search_knowledge()` returns "No results found"

**Solutions**:

```python
from skill_helpers import search_knowledge, get_stats, index_documents

# 1. Check if database has content
print(get_stats())  # Should show > 0 chunks

# 2. Try broader search
results = search_knowledge(query="memoria", limit=10)  # Very broad

# 3. Try different search mode
results = search_knowledge(query="your query", mode="semantic")  # vs hybrid

# 4. Check if documents are indexed
from skill_helpers import list_indexed_documents
print(list_indexed_documents())

# 5. Re-index if needed
print(index_documents())
```

### Issue: Slow Search Performance

**Symptom**: Search takes > 5 seconds

**Solutions**:

```python
# 1. Reduce limit
results = search_knowledge(query="query", limit=3)  # Instead of 10

# 2. Disable query expansion
results = search_knowledge(query="query", expand=False)

# 3. Use semantic-only mode (faster than hybrid)
results = search_knowledge(query="query", mode="semantic")
```

### Issue: Irrelevant Results

**Symptom**: Results don't match query intent

**Solutions**:

```python
# 1. Be more specific
# ❌ Bad: "architecture"
# ✅ Good: "memoria onion architecture pattern"

# 2. Use hybrid mode
results = search_knowledge(query="specific query", mode="hybrid")

# 3. Enable query expansion
results = search_knowledge(query="query", expand=True)

# 4. Request more results and scan
results = search_knowledge(query="query", limit=10)
```

### Issue: ChromaDB Connection Error

**Symptom**: `health_check()` shows ChromaDB not connected

**Solutions**:

```bash
# 1. Check if ChromaDB is running
docker ps | grep chroma

# 2. Check port
lsof -i :8001

# 3. Restart ChromaDB
docker restart chromadb

# 4. Test connection
curl http://localhost:8001/api/v1/heartbeat
```

### Issue: Index Not Updating

**Symptom**: New documents not appearing in search

**Solutions**:

```python
from skill_helpers import index_documents, list_indexed_documents, get_stats

# 1. Check if document is in docs/ directory
print(list_indexed_documents())

# 2. Get chunk count before
before = get_stats()

# 3. Re-index
print(index_documents())

# 4. Get chunk count after
after = get_stats()

# 5. Compare - should increase
print(f"Before: {before}")
print(f"After: {after}")
```

## Best Practices

### Search Query Design

✅ **DO**:
- Use natural language questions
- Include context words ("how", "why", "what")
- Use 5-10 words per query
- Enable hybrid mode for most searches
- Request 3-5 results for general queries

❌ **DON'T**:
- Use single words ("architecture")
- Use > 20 words in a query
- Disable query expansion unless needed
- Request > 10 results (diminishing returns)

### Document Organization

✅ **DO**:
- Organize documents in subdirectories
- Use descriptive filenames
- Keep documents under 50KB
- Use markdown format
- Include metadata in frontmatter

❌ **DON'T**:
- Dump all docs in root directory
- Use generic names ("doc1.md")
- Add binary files
- Use proprietary formats
- Forget to index after adding

### Maintenance Schedule

**Daily** (if active development):
- Add new documents as created
- Check `get_stats()` for growth

**Weekly**:
- Review `list_indexed_documents()`
- Remove outdated documents
- Re-index if significant changes

**Monthly**:
- Full re-index (rebuild=True)
- Review search quality
- Optimize chunk_size if needed
- Clean up orphaned chunks

### Performance Optimization

**Small Knowledge Base** (< 10,000 chunks):
```python
# No optimization needed, all defaults work well
search_knowledge(query="query", mode="hybrid", limit=5)
```

**Medium Knowledge Base** (10,000 - 100,000 chunks):
```python
# Reduce limits, disable expansion if needed
search_knowledge(query="query", mode="hybrid", limit=3, expand=False)
```

**Large Knowledge Base** (> 100,000 chunks):
```python
# Use semantic-only, lower limits
search_knowledge(query="query", mode="semantic", limit=3, expand=False)
```

### Integration with Claude Code

**Pattern**: Always query RAG before responding to non-trivial requests

```python
from skill_helpers import search_knowledge

# User asks: "How do I configure chronos?"

# 1. Query RAG first
docs = search_knowledge(
    query="chronos configuration setup",
    mode="hybrid",
    limit=5
)

# 2. Process results
# ... Claude reads docs and formulates answer

# 3. Provide answer to user based on RAG results
```

**Why**: This ensures Claude always has fresh, accurate information from your documentation rather than relying on training data.

## Advanced Usage

### Custom Adapter Configuration

For advanced use cases, configure adapters directly:

```python
from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
from memoria.adapters.sentence_transformers.sentence_transformer_adapter import SentenceTransformerAdapter
from memoria.adapters.search.search_engine_adapter import SearchEngineAdapter

# Custom ChromaDB settings
vector_store = ChromaDBAdapter(
    collection_name="custom_collection",
    use_http=True,
    http_host="localhost",
    http_port=8001
)

# Custom embedding model
embedder = SentenceTransformerAdapter(
    model_name="all-mpnet-base-v2"  # Higher quality, slower
)

# Custom search weights
search_engine = SearchEngineAdapter(
    vector_store,
    embedder,
    hybrid_weight=0.8  # 80% semantic, 20% BM25
)

# Perform search
results = search_engine.search(
    query="your query",
    limit=5,
    mode="hybrid"
)
```

### Batch Processing

```python
from skill_helpers import search_knowledge

# Process multiple queries efficiently
queries = [
    "memoria architecture",
    "chronos scheduling",
    "workdiary implementation"
]

results_map = {}
for query in queries:
    results_map[query] = search_knowledge(
        query=query,
        mode="hybrid",
        limit=3
    )

# Process results
for query, results in results_map.items():
    print(f"\n## {query}")
    print(results)
```

## Summary

### Quick Reference Card

| Task | Command |
|------|---------|
| Check health | `health_check()` |
| Search | `search_knowledge(query, mode="hybrid", limit=5)` |
| Index docs | `index_documents()` |
| Add doc | `add_document(path, reindex=True)` |
| List docs | `list_indexed_documents()` |
| Get stats | `get_stats()` |

### Search Mode Decision Tree

```
Need exact keyword match? → mode="hybrid"
    ↓
Need semantic understanding? → mode="semantic"
    ↓
Not sure? → mode="hybrid" (default, best balance)
```

### When to Use Each Function

- **health_check()**: Start of session, after problems
- **search_knowledge()**: Every time you need information
- **index_documents()**: After adding docs, weekly maintenance
- **add_document()**: Adding single documents
- **list_indexed_documents()**: Understanding document structure
- **get_stats()**: Before/after operations, monitoring

### Common Gotchas

1. **Forgot to activate venv**: Always `source .venv/bin/activate`
2. **ChromaDB not running**: Check `docker ps | grep chroma`
3. **Documents not indexed**: Run `index_documents()` after adding
4. **No results**: Try broader query or different search mode
5. **Slow performance**: Reduce limit, disable expansion

## Next Steps

1. Read `README.md` for architecture details
2. Try the quick start examples
3. Experiment with different search modes
4. Integrate into your Claude Code workflow
5. Set up maintenance schedule

For detailed API documentation, see `README.md`.

For troubleshooting, see the Troubleshooting section above.

For advanced patterns, see Integration Patterns section above.
