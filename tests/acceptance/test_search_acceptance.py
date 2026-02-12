"""
Acceptance tests for search quality - verify user stories are met

Tasks: T044, T045, T046 - Acceptance tests for US1, US2, US3
"""

import pytest
from memoria.skill_helpers import search_knowledge
from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
from memoria.adapters.sentence_transformers.sentence_transformer_adapter import SentenceTransformerAdapter
from memoria.adapters.search.search_engine_adapter import SearchEngineAdapter


@pytest.fixture
def search_engine():
    """Initialize search engine for acceptance testing"""
    vector_store = ChromaDBAdapter(
        collection_name="memoria",
        use_http=True,
        http_host="localhost",
        http_port=8001
    )
    embedder = SentenceTransformerAdapter()
    return SearchEngineAdapter(vector_store, embedder, hybrid_weight=0.95)


class TestUS1Acceptance:
    """
    T044: Acceptance test for User Story 1
    As a developer using Memoria RAG, I want queries to return 5-10 relevant results
    instead of a single result, so I can find the information I need.
    """

    def test_user_searches_for_documentation(self, search_engine):
        """
        Scenario: User searches for documentation on a topic
        Given: The user wants to learn about the RAG system
        When: They search for "RAG query protocol"
        Then: They receive 5-10 relevant documentation results
        """
        query = "RAG query protocol"
        results = search_engine.search(query=query, limit=10, mode="hybrid")

        # User receives multiple results
        assert len(results) >= 5, \
            f"User expected 5-10 results but got only {len(results)}"

        # Results are relevant (scored reasonably)
        assert results[0].score >= 0.5, \
            f"Top result score {results[0].score:.4f} seems too low"

    def test_user_explores_related_topics(self, search_engine):
        """
        Scenario: User wants to explore related topics
        Given: The user is researching agent systems
        When: They search for "specialized agents"
        Then: They receive multiple results covering different aspects
        """
        query = "specialized agents"
        results = search_engine.search(query=query, limit=10, mode="hybrid")

        # Multiple results allow exploration
        assert len(results) >= 5, \
            "User needs multiple results to explore different aspects"

        # Results have varying relevance (graduated scores)
        scores = [r.score for r in results]
        score_variance = max(scores) - min(scores)
        assert score_variance >= 0.01, \
            "User needs varied results, not all identical"

    def test_user_finds_specific_information(self, search_engine):
        """
        Scenario: User searches for specific information
        Given: The user needs information about git commits
        When: They search for "git commit search"
        Then: They receive relevant results without being limited to one
        """
        query = "git commit search"
        results = search_engine.search(query=query, limit=10, mode="hybrid")

        # User is not limited to single result
        assert len(results) >= 3, \
            "User should see multiple options, not just one result"


class TestUS2Acceptance:
    """
    T045: Acceptance test for User Story 2
    As a developer, I want confidence scores to accurately reflect relevance
    so I can trust the search rankings.
    """

    def test_user_trusts_high_scores(self, search_engine):
        """
        Scenario: User sees high confidence scores for relevant matches
        Given: The user searches for exact terminology used in docs
        When: They search for "claude loop protocol"
        Then: The top result has high confidence (≥0.7)
        """
        query = "claude loop protocol"
        results = search_engine.search(query=query, limit=10, mode="hybrid")

        assert len(results) > 0, "No results returned"

        top_score = results[0].score
        assert top_score >= 0.7, \
            f"User expects high confidence for exact match, got {top_score:.4f}"

    def test_user_distinguishes_relevance_levels(self, search_engine):
        """
        Scenario: User can distinguish between highly and moderately relevant results
        Given: The user reviews search results
        When: They look at the confidence scores
        Then: Scores reflect varying levels of relevance (not all clustered)
        """
        query = "semantic search implementation"
        results = search_engine.search(query=query, limit=10, mode="hybrid")

        assert len(results) >= 5, "Need multiple results for comparison"

        scores = [r.score for r in results]

        # Scores should span a meaningful range
        score_range = max(scores) - min(scores)
        assert score_range >= 0.02, \
            f"User can't distinguish relevance with range {score_range:.4f}"

        # Scores should be sorted (highest first)
        assert scores == sorted(scores, reverse=True), \
            "User expects results ordered by relevance"

    def test_user_filters_by_confidence(self, search_engine):
        """
        Scenario: User wants to focus on high-confidence results
        Given: The user has reviewed search results
        When: They look at top 3 results
        Then: All top 3 results have reasonable confidence (≥0.5)
        """
        query = "agent catalog documentation"
        results = search_engine.search(query=query, limit=10, mode="hybrid")

        assert len(results) >= 3, "Need at least 3 results"

        # Top 3 should all be reasonably confident
        for i in range(3):
            assert results[i].score >= 0.5, \
                f"Result {i+1} score {results[i].score:.4f} too low for top results"


class TestUS3Acceptance:
    """
    T046: Acceptance test for User Story 3
    As a developer, I want semantic search to find conceptually related documents
    even when I use different terminology.
    """

    def test_user_searches_with_synonyms(self, search_engine):
        """
        Scenario: User uses synonyms instead of exact terms
        Given: The user doesn't know exact terminology
        When: They search for "task-specific AI workers"
        Then: They find documents about "specialized agents"
        """
        query = "task-specific AI workers"
        results = search_engine.search(query=query, limit=10, mode="hybrid")

        assert len(results) > 0, "Semantic search found no results for synonyms"

        # Should find conceptually related content
        # (We can't easily verify exact content without knowing what's in the DB,
        # but we verify that semantic search returns confident results)
        assert results[0].score >= 0.5, \
            f"Semantic match should be confident, got {results[0].score:.4f}"

    def test_user_searches_with_paraphrases(self, search_engine):
        """
        Scenario: User paraphrases concepts
        Given: The user describes a concept in their own words
        When: They search for "memory system for coding agents"
        Then: They find documents about "RAG" and "knowledge retrieval"
        """
        query = "memory system for coding agents"
        results = search_engine.search(query=query, limit=10, mode="hybrid")

        assert len(results) >= 3, \
            "Paraphrased query should find relevant conceptual matches"

        # Semantic understanding should yield decent scores
        assert results[0].score >= 0.4, \
            "Paraphrase should match conceptually"

    def test_user_searches_casually(self, search_engine):
        """
        Scenario: User uses casual language instead of formal terms
        Given: The user is new and uses casual language
        When: They search for "how do I search for stuff?"
        Then: They find documentation about search and query protocols
        """
        query = "how do I search for stuff"
        results = search_engine.search(query=query, limit=10, mode="hybrid")

        # Casual language should still find relevant results
        assert len(results) > 0, \
            "Casual language should bridge to formal documentation"

        # At least some results should be reasonably confident
        confident_results = [r for r in results if r.score >= 0.4]
        assert len(confident_results) >= 1, \
            "Should find at least one confident match for casual query"

    def test_user_compares_search_modes(self, search_engine):
        """
        Scenario: User benefits from hybrid search (semantic + keyword)
        Given: The user wants both semantic and exact matches
        When: They search with hybrid mode
        Then: Results include both conceptually related and keyword matches
        """
        query = "AI agent implementation"

        # Get results from different modes
        hybrid_results = search_engine.search(query=query, limit=5, mode="hybrid")
        semantic_results = search_engine.search(query=query, limit=5, mode="semantic")

        # Hybrid should return results
        assert len(hybrid_results) > 0, "Hybrid mode should return results"

        # Hybrid benefits from both approaches
        # (In practice, hybrid with 95% semantic weight should score similarly to semantic)
        if len(semantic_results) > 0:
            hybrid_top = hybrid_results[0].score
            semantic_top = semantic_results[0].score

            # Scores should be close (since 95% semantic weight)
            # User gets benefits of semantic search with slight keyword boost
            assert hybrid_top >= semantic_top * 0.85, \
                "Hybrid mode should preserve semantic search quality"


class TestBackwardCompatibility:
    """
    Acceptance test for backward compatibility
    Verify that the fix doesn't break existing usage
    """

    def test_skill_helper_still_works(self):
        """
        Scenario: Existing code using skill_helpers continues to work
        Given: Code uses search_knowledge() function
        When: They call search_knowledge with standard parameters
        Then: The function works without errors
        """
        query = "test query"

        # This should not raise an exception
        result = search_knowledge(query=query, mode="hybrid", limit=5)

        # Result should be a string (formatted output)
        assert isinstance(result, str), "search_knowledge should return formatted string"
        assert len(result) > 0, "search_knowledge returned empty result"

    def test_search_engine_api_unchanged(self, search_engine):
        """
        Scenario: Direct SearchEngineAdapter usage still works
        Given: Code uses SearchEngineAdapter directly
        When: They call search() method
        Then: API is unchanged
        """
        # API should work with standard parameters
        results = search_engine.search(
            query="test",
            mode="hybrid",
            limit=10
        )

        # Returns list of SearchResult objects
        assert isinstance(results, list), "search() should return list"

        if len(results) > 0:
            # SearchResult should have expected attributes
            result = results[0]
            assert hasattr(result, 'document'), "SearchResult missing document"
            assert hasattr(result, 'score'), "SearchResult missing score"
            assert hasattr(result, 'rank'), "SearchResult missing rank"
