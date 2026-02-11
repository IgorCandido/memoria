"""Search Knowledge Use Case.

Clean architecture implementation for RAG search operations.
"""

from dataclasses import dataclass
from typing import List, Literal

from memoria.domain.entities import SearchResult
from memoria.domain.ports.search_engine import SearchEnginePort
from memoria.domain.ports.embedding_generator import EmbeddingGeneratorPort


@dataclass(frozen=True)
class SearchKnowledgeRequest:
    """Request for knowledge search operation."""

    query: str
    mode: Literal["semantic", "bm25", "hybrid"] = "hybrid"
    limit: int = 5
    expand: bool = True

    def __post_init__(self) -> None:
        """Validate request parameters."""
        if not self.query or not self.query.strip():
            raise ValueError("Query cannot be empty")
        if self.limit <= 0:
            raise ValueError("Limit must be positive")
        if self.limit > 100:
            raise ValueError("Limit cannot exceed 100")


@dataclass(frozen=True)
class SearchKnowledgeResponse:
    """Response from knowledge search operation."""

    results: List[SearchResult]
    total: int
    query_expanded: bool
    expanded_terms: List[str]


class SearchKnowledgeUseCase:
    """Use case for searching the knowledge base.

    This use case orchestrates the search operation using the search engine
    and embedding generator adapters.
    """

    def __init__(
        self, search_engine: SearchEnginePort, embedder: EmbeddingGeneratorPort
    ) -> None:
        """Initialize the use case.

        Args:
            search_engine: Port for search operations
            embedder: Port for generating embeddings
        """
        self._search_engine = search_engine
        self._embedder = embedder

    def execute(self, request: SearchKnowledgeRequest) -> SearchKnowledgeResponse:
        """Execute the search operation.

        Args:
            request: Search request with query and parameters

        Returns:
            SearchKnowledgeResponse with results and metadata
        """
        # Query expansion (if enabled)
        query_terms = [request.query]
        query_expanded = False

        if request.expand:
            # Simple expansion: keep original query for now
            # TODO: Implement actual query expansion logic
            query_expanded = True
            query_terms = [request.query]  # For now, just the original term

        # Perform search
        results = self._search_engine.search(
            query=request.query, limit=request.limit, mode=request.mode
        )

        return SearchKnowledgeResponse(
            results=results,
            total=len(results),
            query_expanded=query_expanded,
            expanded_terms=query_terms,
        )
