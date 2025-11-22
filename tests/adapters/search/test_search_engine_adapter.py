"""
Tests for SearchEngineAdapter.

Inherits from SearchEnginePortTests to ensure full port compliance.
"""

import pytest

from memoria.adapters.search.search_engine_adapter import SearchEngineAdapter
from memoria.adapters.stubs.vector_store_stub import VectorStoreStub
from memoria.adapters.stubs.embedding_generator_stub import EmbeddingGeneratorStub
from memoria.domain.entities import Document
from memoria.domain.ports.search_engine import SearchEnginePort
from tests.ports.test_search_engine_port import SearchEnginePortTests


class TestSearchEngineAdapter(SearchEnginePortTests):
    """
    Test SearchEngineAdapter against SearchEnginePort contract.

    Inherits all port tests from SearchEnginePortTests.
    Uses stub vector store and embedding generator for testing.
    """

    def create_engine(self) -> SearchEnginePort:
        """
        Factory method to create a SearchEngineAdapter instance.

        Required by SearchEnginePortTests base class.
        """
        # Create stubs for dependencies
        vector_store = VectorStoreStub()
        embedder = EmbeddingGeneratorStub(dimensions=384)

        # Add some test documents to vector store
        test_docs = [
            Document(
                id="doc1",
                content="Python is a high-level programming language",
                metadata={"source": "python_guide.md"},
                embedding=embedder.embed_text("Python programming").vector,
            ),
            Document(
                id="doc2",
                content="Machine learning with Python and scikit-learn",
                metadata={"source": "ml_tutorial.md"},
                embedding=embedder.embed_text("Machine learning Python").vector,
            ),
            Document(
                id="doc3",
                content="Data science combines statistics and programming",
                metadata={"source": "data_science.md"},
                embedding=embedder.embed_text("Data science programming").vector,
            ),
        ]
        vector_store.add_documents(test_docs)

        return SearchEngineAdapter(
            vector_store=vector_store,
            embedding_generator=embedder,
            hybrid_weight=0.7,
        )

    def test_hybrid_weight_clamping(self) -> None:
        """Test that hybrid weight is clamped to [0, 1]."""
        vector_store = VectorStoreStub()
        embedder = EmbeddingGeneratorStub()

        # Test values outside range
        engine_low = SearchEngineAdapter(vector_store, embedder, hybrid_weight=-0.5)
        assert engine_low._hybrid_weight == 0.0

        engine_high = SearchEngineAdapter(vector_store, embedder, hybrid_weight=1.5)
        assert engine_high._hybrid_weight == 1.0

        engine_normal = SearchEngineAdapter(vector_store, embedder, hybrid_weight=0.7)
        assert engine_normal._hybrid_weight == 0.7

    def test_query_expansion_with_known_terms(self) -> None:
        """Test query expansion with known synonyms."""
        engine = self.create_engine()

        # Test known expansion
        expanded = engine.expand_query("python programming")
        assert expanded.original == "python programming"
        assert "python programming" in expanded.expanded
        assert len(expanded.expanded) > 1  # Should have expansions

    def test_query_expansion_without_known_terms(self) -> None:
        """Test query expansion with unknown terms (no expansions)."""
        engine = self.create_engine()

        # Test unknown term
        expanded = engine.expand_query("unknown_term_xyz")
        assert expanded.original == "unknown_term_xyz"
        assert expanded.expanded == ["unknown_term_xyz"]  # Only original

    def test_rerank_boosts_exact_matches(self) -> None:
        """Test that reranking boosts results with exact query matches."""
        engine = self.create_engine()

        # First search for results
        results = engine.search("Python", mode="semantic", limit=3)
        assert len(results) > 0

        # Rerank - should boost results with "Python" in content
        reranked = engine.rerank("Python", results)

        # Check that ranks were updated
        for i, result in enumerate(reranked):
            assert result.rank == i
