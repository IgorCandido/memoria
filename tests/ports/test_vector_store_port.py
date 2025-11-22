"""
Port test base class for VectorStorePort.

All VectorStore adapters (ChromaDB, Pinecone, etc.) must pass these tests
by inheriting from this class and implementing create_store().
"""

from abc import ABC, abstractmethod

import pytest

from memoria.domain.entities import Document, SearchResult
from memoria.domain.ports.vector_store import VectorStorePort


class VectorStorePortTests(ABC):
    """
    Base test suite for all VectorStore adapters.

    To test a new adapter:
    1. Inherit from this class
    2. Implement create_store() to return your adapter
    3. Run pytest - all tests execute automatically

    Example:
        class TestMyAdapter(VectorStorePortTests):
            def create_store(self) -> VectorStorePort:
                return MyVectorStoreAdapter(...)
    """

    @abstractmethod
    def create_store(self) -> VectorStorePort:
        """
        Factory method - subclasses must implement.

        Returns:
            A configured instance of the adapter under test
        """
        ...

    @pytest.fixture
    def store(self) -> VectorStorePort:
        """Fixture that provides a fresh store for each test."""
        store = self.create_store()
        store.clear()  # Ensure clean state
        return store

    @pytest.fixture
    def sample_doc(self) -> Document:
        """Fixture providing a sample document with embedding."""
        return Document(
            id="doc1",
            content="Python is a programming language",
            metadata={"source": "test.txt", "lang": "en"},
            embedding=[0.1, 0.2, 0.3, 0.4],
        )

    def test_add_documents_single(self, store: VectorStorePort, sample_doc: Document) -> None:
        """Test adding a single document."""
        store.add_documents([sample_doc])
        stats = store.get_stats()
        assert stats["document_count"] >= 1

    def test_add_documents_batch(self, store: VectorStorePort) -> None:
        """Test adding multiple documents at once."""
        docs = [
            Document(
                id=f"doc{i}",
                content=f"Content {i}",
                metadata={"index": str(i)},
                embedding=[0.1 * i, 0.2 * i, 0.3 * i, 0.4 * i],
            )
            for i in range(5)
        ]
        store.add_documents(docs)
        stats = store.get_stats()
        assert stats["document_count"] >= 5

    def test_search_returns_results(self, store: VectorStorePort, sample_doc: Document) -> None:
        """Test that search returns relevant results."""
        store.add_documents([sample_doc])
        results = store.search(query_embedding=[0.1, 0.2, 0.3, 0.4], k=1)
        assert len(results) >= 1
        assert isinstance(results[0], SearchResult)
        assert 0.0 <= results[0].score <= 1.0

    def test_search_respects_k_limit(self, store: VectorStorePort) -> None:
        """Test that search returns at most k results."""
        docs = [
            Document(
                id=f"doc{i}",
                content=f"Content {i}",
                metadata={},
                embedding=[0.1 * i] * 4,
            )
            for i in range(10)
        ]
        store.add_documents(docs)

        results = store.search(query_embedding=[0.5, 0.5, 0.5, 0.5], k=3)
        assert len(results) <= 3

    def test_search_orders_by_relevance(self, store: VectorStorePort) -> None:
        """Test that search results are ordered by relevance (score)."""
        docs = [
            Document(
                id=f"doc{i}",
                content=f"Content {i}",
                metadata={},
                embedding=[0.1 * i] * 4,
            )
            for i in range(5)
        ]
        store.add_documents(docs)

        results = store.search(query_embedding=[0.3, 0.3, 0.3, 0.3], k=5)
        # Results should be ordered by score (highest first)
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    def test_get_by_id_existing(self, store: VectorStorePort, sample_doc: Document) -> None:
        """Test retrieving an existing document by ID."""
        store.add_documents([sample_doc])
        retrieved = store.get_by_id("doc1")
        assert retrieved is not None
        assert retrieved.id == "doc1"
        assert retrieved.content == sample_doc.content

    def test_get_by_id_nonexistent(self, store: VectorStorePort) -> None:
        """Test retrieving a non-existent document returns None."""
        result = store.get_by_id("nonexistent")
        assert result is None

    def test_delete_existing(self, store: VectorStorePort, sample_doc: Document) -> None:
        """Test deleting an existing document."""
        store.add_documents([sample_doc])
        result = store.delete("doc1")
        assert result is True
        # Verify it's actually deleted
        retrieved = store.get_by_id("doc1")
        assert retrieved is None

    def test_delete_nonexistent(self, store: VectorStorePort) -> None:
        """Test deleting a non-existent document returns False."""
        result = store.delete("nonexistent")
        assert result is False

    def test_get_stats(self, store: VectorStorePort, sample_doc: Document) -> None:
        """Test getting store statistics."""
        store.add_documents([sample_doc])
        stats = store.get_stats()
        assert isinstance(stats, dict)
        assert "document_count" in stats
        assert stats["document_count"] >= 1

    def test_clear(self, store: VectorStorePort, sample_doc: Document) -> None:
        """Test clearing all documents from the store."""
        store.add_documents([sample_doc])
        store.clear()
        stats = store.get_stats()
        assert stats["document_count"] == 0

    def test_search_empty_store(self, store: VectorStorePort) -> None:
        """Test searching an empty store returns no results."""
        results = store.search(query_embedding=[0.1, 0.2, 0.3, 0.4], k=5)
        assert len(results) == 0
