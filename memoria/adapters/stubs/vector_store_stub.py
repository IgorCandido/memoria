"""
In-memory stub implementation of VectorStorePort.

This stub passes all VectorStorePortTests and can be used for testing
the application layer without needing a real vector database.
"""

from typing import Optional

from memoria.domain.entities import Document, SearchResult
from memoria.domain.value_objects import Score


class VectorStoreStub:
    """
    In-memory stub for VectorStorePort.

    Stores documents in a dictionary and uses simple cosine similarity
    for search (not optimized, just functional for testing).
    """

    def __init__(self) -> None:
        """Initialize empty in-memory store."""
        self._documents: dict[str, Document] = {}

    def add_documents(self, docs: list[Document]) -> None:
        """Add documents to in-memory store."""
        for doc in docs:
            if doc.embedding is None:
                raise ValueError(f"Document {doc.id} is missing embedding")
            self._documents[doc.id] = doc

    def search(self, query_embedding: list[float], k: int) -> list[SearchResult]:
        """
        Search using simple cosine similarity.

        Note: This is a naive implementation for testing only.
        Real implementations use optimized vector search (HNSW, IVF, etc.).
        """
        if k < 1:
            raise ValueError(f"k must be positive, got {k}")

        if not self._documents:
            return []

        # Calculate similarity scores
        results: list[tuple[Document, float]] = []
        for doc in self._documents.values():
            if doc.embedding is None:
                continue

            # Cosine similarity
            similarity = self._cosine_similarity(query_embedding, doc.embedding)
            results.append((doc, similarity))

        # Sort by similarity (highest first) and take top k
        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:k]

        # Convert to SearchResult entities
        search_results = [
            SearchResult(document=doc, score=score, rank=rank)
            for rank, (doc, score) in enumerate(results)
        ]

        return search_results

    def get_by_id(self, doc_id: str) -> Optional[Document]:
        """Retrieve document by ID."""
        return self._documents.get(doc_id)

    def delete(self, doc_id: str) -> bool:
        """Delete document by ID."""
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False

    def get_stats(self) -> dict[str, int]:
        """Get statistics about the store."""
        return {
            "document_count": len(self._documents),
        }

    def clear(self) -> None:
        """Remove all documents."""
        self._documents.clear()

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Returns a score in [0, 1] where 1 is most similar.
        """
        if len(vec1) != len(vec2):
            raise ValueError(
                f"Vector dimensions must match: {len(vec1)} != {len(vec2)}"
            )

        # Dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # Magnitudes
        mag1 = sum(a * a for a in vec1) ** 0.5
        mag2 = sum(b * b for b in vec2) ** 0.5

        if mag1 == 0 or mag2 == 0:
            return 0.0

        # Cosine similarity [-1, 1]
        similarity = dot_product / (mag1 * mag2)

        # Normalize to [0, 1]
        normalized = (similarity + 1.0) / 2.0

        # Clamp to [0, 1] to handle floating point errors
        return max(0.0, min(1.0, float(normalized)))
