"""
Port test base class for SearchEnginePort.

All SearchEngine adapters must pass these tests.
"""

from abc import ABC, abstractmethod

import pytest

from memoria.domain.entities import Document, SearchResult
from memoria.domain.ports.search_engine import SearchEnginePort
from memoria.domain.value_objects import QueryTerms


class SearchEnginePortTests(ABC):
    """
    Base test suite for all SearchEngine adapters.

    To test a new adapter:
    1. Inherit from this class
    2. Implement create_engine() to return your adapter
    3. Optionally implement index_test_documents() for setup
    4. Run pytest - all tests execute automatically
    """

    @abstractmethod
    def create_engine(self) -> SearchEnginePort:
        """
        Factory method - subclasses must implement.

        Returns:
            A configured instance of the adapter under test
        """
        ...

    def index_test_documents(self, engine: SearchEnginePort) -> None:
        """
        Optional hook for subclasses to index test documents.

        Override this if your adapter needs documents indexed before search.
        Default implementation does nothing.
        """
        pass

    @pytest.fixture
    def engine(self) -> SearchEnginePort:
        """Fixture that provides a search engine for each test."""
        engine = self.create_engine()
        self.index_test_documents(engine)
        return engine

    def test_search_returns_results(self, engine: SearchEnginePort) -> None:
        """Test that search returns a list of SearchResults."""
        results = engine.search(query="test query", mode="semantic", limit=5)
        assert isinstance(results, list)
        assert all(isinstance(r, SearchResult) for r in results)

    def test_search_respects_limit(self, engine: SearchEnginePort) -> None:
        """Test that search returns at most limit results."""
        results = engine.search(query="test", mode="hybrid", limit=3)
        assert len(results) <= 3

    def test_search_semantic_mode(self, engine: SearchEnginePort) -> None:
        """Test search with semantic mode."""
        results = engine.search(query="python programming", mode="semantic", limit=5)
        assert isinstance(results, list)

    def test_search_bm25_mode(self, engine: SearchEnginePort) -> None:
        """Test search with BM25 mode."""
        results = engine.search(query="python programming", mode="bm25", limit=5)
        assert isinstance(results, list)

    def test_search_hybrid_mode(self, engine: SearchEnginePort) -> None:
        """Test search with hybrid mode."""
        results = engine.search(query="python programming", mode="hybrid", limit=5)
        assert isinstance(results, list)

    def test_search_results_ordered_by_score(self, engine: SearchEnginePort) -> None:
        """Test that search results are ordered by relevance score."""
        results = engine.search(query="test", mode="hybrid", limit=10)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].score >= results[i + 1].score

    def test_expand_query_returns_query_terms(self, engine: SearchEnginePort) -> None:
        """Test that expand_query returns QueryTerms."""
        terms = engine.expand_query("python")
        assert isinstance(terms, QueryTerms)
        assert terms.original == "python"
        assert len(terms.expanded) > 0

    def test_expand_query_includes_original(self, engine: SearchEnginePort) -> None:
        """Test that expanded terms include original query."""
        query = "machine learning"
        terms = engine.expand_query(query)
        assert query in terms.all_terms

    def test_rerank_returns_results(self, engine: SearchEnginePort) -> None:
        """Test that rerank returns a list of SearchResults."""
        # Create some mock results
        doc = Document(id="doc1", content="test", metadata={}, embedding=[0.1] * 4)
        initial_results = [
            SearchResult(document=doc, score=0.5, rank=0),
            SearchResult(document=doc, score=0.3, rank=1),
        ]

        reranked = engine.rerank(query="test", results=initial_results)
        assert isinstance(reranked, list)
        assert len(reranked) == len(initial_results)
        assert all(isinstance(r, SearchResult) for r in reranked)

    def test_rerank_preserves_all_results(self, engine: SearchEnginePort) -> None:
        """Test that rerank returns all input results (possibly reordered)."""
        doc1 = Document(id="doc1", content="first", metadata={}, embedding=[0.1] * 4)
        doc2 = Document(id="doc2", content="second", metadata={}, embedding=[0.2] * 4)

        initial_results = [
            SearchResult(document=doc1, score=0.3, rank=0),
            SearchResult(document=doc2, score=0.7, rank=1),
        ]

        reranked = engine.rerank(query="test", results=initial_results)
        assert len(reranked) == 2
        # All original documents should be present
        reranked_ids = {r.document.id for r in reranked}
        assert reranked_ids == {"doc1", "doc2"}
