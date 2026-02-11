"""
SearchEngine adapter implementing SearchEnginePort.

Provides semantic search, BM25 keyword search, and hybrid search capabilities.
Includes query expansion and result reranking.
"""

import os
import time

from memoria.domain.entities import Document, SearchResult
from memoria.domain.ports.search_engine import SearchEnginePort
from memoria.domain.ports.vector_store import VectorStorePort
from memoria.domain.ports.embedding_generator import EmbeddingGeneratorPort
from memoria.domain.value_objects import QueryTerms, SearchMode


class SearchEngineAdapter:
    """
    Adapter for search operations combining semantic and keyword search.

    Implements SearchEnginePort protocol with hybrid search capabilities.
    """

    def __init__(
        self,
        vector_store: VectorStorePort,
        embedding_generator: EmbeddingGeneratorPort,
        hybrid_weight: float = 0.95,
    ) -> None:
        """
        Initialize search engine adapter.

        Args:
            vector_store: Vector store for document retrieval
            embedding_generator: Generator for query embeddings
            hybrid_weight: Weight for semantic vs keyword (0.0-1.0, higher = more semantic)
                          Default 0.95 (95% semantic, 5% BM25) to prevent score compression
        """
        self._vector_store = vector_store
        self._embedder = embedding_generator
        self._hybrid_weight = max(0.0, min(1.0, hybrid_weight))

        # Simple query expansion dictionary (can be extended)
        self._expansions = {
            "python": ["python", "py", "programming"],
            "ml": ["machine learning", "ml", "artificial intelligence"],
            "ai": ["artificial intelligence", "ai", "machine learning"],
            "api": ["api", "interface", "endpoint"],
        }

    def search(
        self,
        query: str,
        mode: SearchMode = "hybrid",
        limit: int = 5,
    ) -> list[SearchResult]:
        """
        Search for documents matching the query.

        Args:
            query: Search query text
            mode: Search mode (semantic, bm25, or hybrid)
            limit: Maximum number of results

        Returns:
            List of search results sorted by relevance
        """
        if mode == "semantic":
            return self._semantic_search(query, limit)
        elif mode == "bm25":
            return self._bm25_search(query, limit)
        else:  # hybrid
            return self._hybrid_search(query, limit)

    def _semantic_search(self, query: str, limit: int) -> list[SearchResult]:
        """Perform semantic vector similarity search."""
        # Generate query embedding
        t0 = time.time()
        query_embedding = self._embedder.embed_text(query)
        embed_ms = (time.time() - t0) * 1000

        # Search vector store
        t1 = time.time()
        results = self._vector_store.search(
            query_embedding=query_embedding.vector,
            k=limit,
        )
        search_ms = (time.time() - t1) * 1000

        if os.getenv("MEMORIA_DEBUG"):
            print(f"[PERF] semantic_search: embed={embed_ms:.1f}ms, "
                  f"chromadb={search_ms:.1f}ms, results={len(results)}")

        return results

    def _bm25_search(self, query: str, limit: int) -> list[SearchResult]:
        """
        Perform BM25 keyword search.

        Simple implementation: term frequency with document length normalization.
        """
        query_terms = query.lower().split()

        # Get all documents from vector store
        # Note: In production, this would use a dedicated text index
        stats = self._vector_store.get_stats()
        if stats.get("document_count", 0) == 0:
            return []

        # For now, we'll use semantic search to get candidates,
        # then rerank by keyword relevance
        # (This is a simplified implementation)
        query_embedding = self._embedder.embed_text(query)
        candidates = self._vector_store.search(
            query_embedding=query_embedding.vector,
            k=limit * 2,  # Get more candidates for reranking
        )

        # Score by keyword presence
        scored_results: list[tuple[SearchResult, float]] = []
        for result in candidates:
            content_lower = result.document.content.lower()
            keyword_score = sum(
                content_lower.count(term) for term in query_terms
            ) / max(len(result.document.content), 1)

            scored_results.append((result, keyword_score))

        # Sort by keyword score
        scored_results.sort(key=lambda x: x[1], reverse=True)

        # Return top results with updated scores
        return [
            SearchResult(
                document=result.document,
                score=min(1.0, keyword_score),
                rank=i,
            )
            for i, (result, keyword_score) in enumerate(scored_results[:limit])
        ]

    def _hybrid_search(self, query: str, limit: int) -> list[SearchResult]:
        """
        Perform hybrid search combining semantic and keyword search.

        Combines scores using weighted average.
        """
        t0 = time.time()

        # Get semantic results
        semantic_results = self._semantic_search(query, limit * 2)

        # Get keyword results
        keyword_results = self._bm25_search(query, limit * 2)

        # Combine scores
        doc_scores: dict[str, tuple[Document, float, float]] = {}

        # Add semantic scores
        for result in semantic_results:
            doc_id = result.document.id
            doc_scores[doc_id] = (result.document, result.score, 0.0)

        # Add/update with keyword scores
        for result in keyword_results:
            doc_id = result.document.id
            if doc_id in doc_scores:
                doc, semantic_score, _ = doc_scores[doc_id]
                doc_scores[doc_id] = (doc, semantic_score, result.score)
            else:
                doc_scores[doc_id] = (result.document, 0.0, result.score)

        # Calculate hybrid scores
        hybrid_results: list[tuple[Document, float]] = []
        for doc_id, (doc, semantic_score, keyword_score) in doc_scores.items():
            hybrid_score = (
                self._hybrid_weight * semantic_score +
                (1.0 - self._hybrid_weight) * keyword_score
            )
            hybrid_results.append((doc, hybrid_score))

        # Sort by hybrid score
        hybrid_results.sort(key=lambda x: x[1], reverse=True)

        # Create SearchResult objects
        final_results = [
            SearchResult(
                document=doc,
                score=score,
                rank=i,
            )
            for i, (doc, score) in enumerate(hybrid_results[:limit])
        ]

        if os.getenv("MEMORIA_DEBUG"):
            hybrid_ms = (time.time() - t0) * 1000
            print(f"[PERF] hybrid_search: total={hybrid_ms:.1f}ms, "
                  f"semantic_count={len(semantic_results)}, "
                  f"keyword_count={len(keyword_results)}, "
                  f"final_count={len(final_results)}")

        return final_results

    def expand_query(self, query: str) -> QueryTerms:
        """
        Expand query with synonyms and related terms.

        Args:
            query: Original query text

        Returns:
            QueryTerms with original and expanded terms
        """
        query_lower = query.lower()
        expanded = [query]  # Always include original

        # Check for known expansions
        for key, synonyms in self._expansions.items():
            if key in query_lower:
                expanded.extend([s for s in synonyms if s != query_lower])

        # Remove duplicates while preserving order
        seen = set()
        unique_expanded = []
        for term in expanded:
            if term not in seen:
                seen.add(term)
                unique_expanded.append(term)

        return QueryTerms(
            original=query,
            expanded=unique_expanded,
        )

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """
        Rerank search results based on query relevance.

        Simple implementation: boosts results with exact query matches.

        Args:
            query: Search query
            results: Initial search results

        Returns:
            Reranked search results
        """
        query_lower = query.lower()

        reranked: list[tuple[SearchResult, float]] = []
        for result in results:
            boost = 1.0

            # Boost if exact query appears in content
            if query_lower in result.document.content.lower():
                boost = 1.2

            # Boost if query appears in metadata (e.g., title, source)
            if any(query_lower in str(v).lower() for v in result.document.metadata.values()):
                boost *= 1.1

            adjusted_score = min(1.0, result.score * boost)
            reranked.append((result, adjusted_score))

        # Sort by adjusted score
        reranked.sort(key=lambda x: x[1], reverse=True)

        # Create new SearchResult objects with updated scores and ranks
        return [
            SearchResult(
                document=result.document,
                score=adjusted_score,
                rank=i,
            )
            for i, (result, adjusted_score) in enumerate(reranked)
        ]
