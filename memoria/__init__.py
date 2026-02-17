"""
Memoria Skill - RAG Search Library

High-level API for Claude Code skills. This library provides direct ChromaDB access
for knowledge base searches, eliminating MCP overhead and reducing token usage by 98.7%.

Based on Memoria Phase 2 (v3.0.0) Onion Architecture.
"""

__version__ = "3.0.0"

__all__ = [
    "search_knowledge",
    "index_documents",
    "add_document",
    "get_stats",
    "health_check",
    "list_indexed_documents",
]


def __getattr__(name):
    """Lazy import from skill_helpers to avoid circular import on 'import memoria'.

    This prevents triggering adapter imports (chromadb, sentence-transformers)
    at package import time, which would fail on systems without those deps installed.
    """
    if name in __all__:
        from memoria import skill_helpers
        return getattr(skill_helpers, name)
    raise AttributeError(f"module 'memoria' has no attribute {name}")
