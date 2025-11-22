"""
Tests for SearchKnowledgeUseCase.

These tests use stub adapters to test application logic in isolation.
No mocks, no real infrastructure - just fast, reliable tests.
"""

import pytest

from memoria.adapters.stubs.embedding_generator_stub import EmbeddingGeneratorStub
from memoria.adapters.stubs.search_engine_stub import SearchEngineStub
from memoria.application.use_cases.search_knowledge import (
    SearchKnowledgeRequest,
    SearchKnowledgeUseCase,
)
from memoria.domain.entities import Document


class TestSearchKnowledgeUseCase:
    """Tests for SearchKnowledgeUseCase using stub adapters."""

    @pytest.fixture
    def search_engine(self) -> SearchEngineStub:
        """Fixture providing a search engine stub with test documents."""
        engine = SearchEngineStub()
        # Index some test documents
        test_docs = [
            Document(
                id="doc1",
                content="Python programming guide",
                metadata={"topic": "programming"},
                embedding=[0.1] * 384,
            ),
            Document(
                id="doc2",
                content="Advanced Python techniques",
                metadata={"topic": "programming"},
                embedding=[0.2] * 384,
            ),
            Document(
                id="doc3",
                content="Machine learning basics",
                metadata={"topic": "ml"},
                embedding=[0.3] * 384,
            ),
        ]
        engine.index_documents(test_docs)
        return engine

    @pytest.fixture
    def embedder(self) -> EmbeddingGeneratorStub:
        """Fixture providing an embedding generator stub."""
        return EmbeddingGeneratorStub(dimensions=384)

    @pytest.fixture
    def use_case(
        self, search_engine: SearchEngineStub, embedder: EmbeddingGeneratorStub
    ) -> SearchKnowledgeUseCase:
        """Fixture providing the use case under test."""
        return SearchKnowledgeUseCase(search_engine=search_engine, embedder=embedder)

    def test_search_with_valid_request(self, use_case: SearchKnowledgeUseCase) -> None:
        """Test search with a valid request returns results."""
        request = SearchKnowledgeRequest(query="Python", mode="hybrid", limit=5)
        response = use_case.execute(request)

        assert response.total >= 0
        assert len(response.results) == response.total
        assert len(response.results) <= 5

    def test_search_respects_limit(self, use_case: SearchKnowledgeUseCase) -> None:
        """Test that search respects the limit parameter."""
        request = SearchKnowledgeRequest(query="Python", limit=1)
        response = use_case.execute(request)

        assert len(response.results) <= 1

    def test_search_with_query_expansion(self, use_case: SearchKnowledgeUseCase) -> None:
        """Test search with query expansion enabled."""
        request = SearchKnowledgeRequest(query="Python", expand=True)
        response = use_case.execute(request)

        assert response.query_expanded is True
        assert len(response.expanded_terms) > 0
        assert "Python" in response.expanded_terms

    def test_search_without_query_expansion(self, use_case: SearchKnowledgeUseCase) -> None:
        """Test search with query expansion disabled."""
        request = SearchKnowledgeRequest(query="Python", expand=False)
        response = use_case.execute(request)

        assert response.query_expanded is False
        assert response.expanded_terms == ["Python"]

    def test_search_with_different_modes(self, use_case: SearchKnowledgeUseCase) -> None:
        """Test search with different search modes."""
        query = "Python"

        # Semantic mode
        request_semantic = SearchKnowledgeRequest(query=query, mode="semantic")
        response_semantic = use_case.execute(request_semantic)
        assert isinstance(response_semantic.total, int)

        # BM25 mode
        request_bm25 = SearchKnowledgeRequest(query=query, mode="bm25")
        response_bm25 = use_case.execute(request_bm25)
        assert isinstance(response_bm25.total, int)

        # Hybrid mode
        request_hybrid = SearchKnowledgeRequest(query=query, mode="hybrid")
        response_hybrid = use_case.execute(request_hybrid)
        assert isinstance(response_hybrid.total, int)

    def test_request_validation_empty_query(self) -> None:
        """Test that empty query raises ValueError."""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            SearchKnowledgeRequest(query="")

    def test_request_validation_whitespace_query(self) -> None:
        """Test that whitespace-only query raises ValueError."""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            SearchKnowledgeRequest(query="   ")

    def test_request_validation_negative_limit(self) -> None:
        """Test that negative limit raises ValueError."""
        with pytest.raises(ValueError, match="Limit must be positive"):
            SearchKnowledgeRequest(query="test", limit=-1)

    def test_request_validation_zero_limit(self) -> None:
        """Test that zero limit raises ValueError."""
        with pytest.raises(ValueError, match="Limit must be positive"):
            SearchKnowledgeRequest(query="test", limit=0)

    def test_request_validation_excessive_limit(self) -> None:
        """Test that limit over 100 raises ValueError."""
        with pytest.raises(ValueError, match="Limit cannot exceed 100"):
            SearchKnowledgeRequest(query="test", limit=101)

    def test_request_immutability(self) -> None:
        """Test that request is immutable."""
        request = SearchKnowledgeRequest(query="test")
        with pytest.raises(AttributeError):
            request.query = "modified"  # type: ignore[misc]

    def test_response_immutability(self, use_case: SearchKnowledgeUseCase) -> None:
        """Test that response is immutable."""
        request = SearchKnowledgeRequest(query="test")
        response = use_case.execute(request)

        with pytest.raises(AttributeError):
            response.total = 99  # type: ignore[misc]
