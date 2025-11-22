"""
Memoria Skill - RAG Search Library

High-level API for Claude Code skills. This library provides direct ChromaDB access
for knowledge base searches, eliminating MCP overhead and reducing token usage by 98.7%.

Based on Memoria Phase 2 (v3.0.0) Onion Architecture.
"""

from memoria.skill_helpers import (
    search_knowledge,
    index_documents,
    add_document,
    get_stats,
    health_check,
    list_indexed_documents,
)

__all__ = [
    "search_knowledge",
    "index_documents",
    "add_document",
    "get_stats",
    "health_check",
    "list_indexed_documents",
]

__version__ = "3.0.0"
