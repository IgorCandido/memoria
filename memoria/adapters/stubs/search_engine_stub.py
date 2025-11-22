"""
Stub implementation of SearchEnginePort.

Provides simple search functionality for testing without requiring
a real search engine infrastructure.
"""

from memoria.domain.entities import Document, SearchResult
from memoria.domain.value_objects import QueryTerms, SearchMode


class SearchEngineStub:
    """
    Stub search engine that provides basic search functionality.

    Uses simple keyword matching and mock query expansion.
    Not semantically meaningful, but sufficient for testing.
    """

    def __init__(self) -> None:
        """Initialize stub search engine with mock document index."""
        # In a real implementation, this would be populated from vector store
        self._documents: list[Document] = []

    def search(self, query: str, mode: SearchMode, limit: int) -> list[SearchResult]:
        """
        Search documents using simple keyword matching.

        Args:
            query: Search query
            mode: Search mode (semantic, bm25, hybrid) - all behave similarly in stub
            limit: Maximum results to return

        Returns:
            List of search results ordered by relevance
        """
        if not query:
            raise ValueError("Query cannot be empty")
        if limit < 1:
            raise ValueError(f"Limit must be positive, got {limit}")

        # Simple keyword matching: count query word occurrences in document
        query_words = query.lower().split()
        results: list[tuple[Document, float]] = []

        for doc in self._documents:
            content_lower = doc.content.lower()
            # Count how many query words appear in document
            matches = sum(1 for word in query_words if word in content_lower)
            if matches > 0:
                # Simple relevance score: percentage of query words found
                score = matches / len(query_words)
                results.append((doc, score))

        # Sort by score (highest first) and take top k
        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:limit]

        # Convert to SearchResult entities
        search_results = [
            SearchResult(document=doc, score=score, rank=rank)
            for rank, (doc, score) in enumerate(results)
        ]

        return search_results

    def expand_query(self, query: str) -> QueryTerms:
        """
        Expand query with mock synonyms/related terms.

        Args:
            query: Original query

        Returns:
            QueryTerms with original and mock expanded terms
        """
        if not query:
            raise ValueError("Query cannot be empty")

        # Simple mock expansion: add "related" variations
        # In real implementation, this would use synonym dictionaries, etc.
        expanded = [query]

        # Add some mock variations
        words = query.split()
        if len(words) == 1:
            # Single word: add plural/singular variations
            if query.endswith("s"):
                expanded.append(query[:-1])  # Remove 's'
            else:
                expanded.append(f"{query}s")  # Add 's'
        else:
            # Multiple words: add individual words
            expanded.extend(words)

        return QueryTerms(original=query, expanded=expanded)

    def rerank(self, query: str, results: list[SearchResult]) -> list[SearchResult]:
        """
        Rerank search results (stub just returns them in same order).

        In a real implementation, this would use a more sophisticated
        model to reorder results for better relevance.

        Args:
            query: Original query
            results: Initial search results

        Returns:
            Reranked results (in stub, just returns input)
        """
        # Stub implementation: return results unchanged
        # Real implementation would use reranking model
        return results

    def index_documents(self, documents: list[Document]) -> None:
        """
        Add documents to the search index (for testing).

        This is a helper method for tests to populate the stub with documents.
        Not part of the SearchEnginePort interface.
        """
        self._documents = documents
