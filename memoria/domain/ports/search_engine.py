"""
SearchEnginePort - Protocol for search operations.

This port defines the contract for searching documents using various
strategies (semantic, keyword, hybrid). The search engine orchestrates
vector search, BM25, reranking, and query expansion.
"""

from typing import Protocol

from ..entities import SearchResult
from ..value_objects import QueryTerms, SearchMode


class SearchEnginePort(Protocol):
    """
    Port for search operations.

    The search engine combines multiple search strategies and provides
    unified search functionality.
    """

    def search(self, query: str, mode: SearchMode, limit: int) -> list[SearchResult]:
        """
        Search for documents matching the query.

        Args:
            query: User's search query
            mode: Search mode (semantic, bm25, or hybrid)
            limit: Maximum number of results to return

        Returns:
            List of search results ordered by relevance (highest first)

        Raises:
            ValueError: If query is empty or limit is invalid
            RuntimeError: If search fails
        """
        ...

    def expand_query(self, query: str) -> QueryTerms:
        """
        Expand query with synonyms, related terms, etc.

        Args:
            query: Original query

        Returns:
            QueryTerms with original and expanded terms

        Raises:
            ValueError: If query is empty
        """
        ...

    def rerank(self, query: str, results: list[SearchResult]) -> list[SearchResult]:
        """
        Rerank search results for better relevance.

        Uses more sophisticated models to reorder results after initial retrieval.

        Args:
            query: Original query
            results: Initial search results to rerank

        Returns:
            Reranked search results
        """
        ...
