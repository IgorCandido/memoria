"""
Integration tests for search quality - verify ChromaDB search fix

Tasks: T041, T042, T043 - Integration tests for US1, US2, US3
"""

import pytest
from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
from memoria.adapters.sentence_transformers.sentence_transformer_adapter import SentenceTransformerAdapter
from memoria.adapters.search.search_engine_adapter import SearchEngineAdapter


@pytest.fixture
def search_engine():
    """Initialize search engine with production configuration"""
    vector_store = ChromaDBAdapter(
        collection_name="memoria",
        use_http=True,
        http_host="localhost",
        http_port=8001
    )
    embedder = SentenceTransformerAdapter()
    return SearchEngineAdapter(vector_store, embedder, hybrid_weight=0.95)


class TestMultiResultSearch:
    """
    T041: Integration test for US1 (multiple results)
    Verify that queries return 5+ results
    """

    def test_diverse_queries_return_multiple_results(self, search_engine):
        """Test that diverse queries all return 5+ results"""
        test_queries = [
            "claude agent",
            "RAG search",
            "git commit",
            "semantic search",
            "memoria system",
        ]

        for query in test_queries:
            results = search_engine.search(query=query, limit=10, mode="hybrid")
            assert len(results) >= 5, f"Query '{query}' returned only {len(results)} results (expected ≥5)"

    def test_minimum_results_returned(self, search_engine):
        """Test that even obscure queries return at least some results"""
        obscure_query = "quantum entanglement photosynthesis"
        results = search_engine.search(query=obscure_query, limit=10, mode="hybrid")

        # Should return some results, even if not highly relevant
        assert len(results) > 0, "Obscure query returned 0 results"

    def test_limit_parameter_respected(self, search_engine):
        """Test that limit parameter controls result count"""
        query = "test query"

        for limit in [1, 5, 10, 20]:
            results = search_engine.search(query=query, limit=limit, mode="hybrid")
            assert len(results) <= limit, f"Returned {len(results)} results with limit={limit}"


class TestConfidenceScoreRanges:
    """
    T042: Integration test for US2 (confidence scores)
    Verify that confidence scores reflect true relevance
    """

    def test_high_relevance_queries_score_above_threshold(self, search_engine):
        """Test that high-relevance queries score ≥0.7"""
        high_relevance_queries = [
            "claude loop protocol",
            "RAG compliance monitoring",
            "agent catalog",
        ]

        for query in high_relevance_queries:
            results = search_engine.search(query=query, limit=10, mode="hybrid")
            assert len(results) > 0, f"No results for query '{query}'"

            top_score = results[0].score
            assert top_score >= 0.7, f"Query '{query}' top score {top_score:.4f} < 0.7"

    def test_graduated_score_distribution(self, search_engine):
        """Test that results have graduated scores (not all identical)"""
        query = "semantic search algorithm"
        results = search_engine.search(query=query, limit=10, mode="hybrid")

        assert len(results) >= 5, "Insufficient results for score distribution test"

        scores = [r.score for r in results]

        # Scores should be in descending order
        assert scores == sorted(scores, reverse=True), "Scores not in descending order"

        # Should have some variation (not all exactly the same)
        score_range = max(scores) - min(scores)
        assert score_range > 0.01, f"Scores too clustered (range: {score_range:.4f})"

    def test_score_bounds(self, search_engine):
        """Test that all scores are within [0.0, 1.0] bounds"""
        query = "test query"
        results = search_engine.search(query=query, limit=10, mode="hybrid")

        for i, result in enumerate(results):
            assert 0.0 <= result.score <= 1.0, \
                f"Result {i} score {result.score} out of bounds [0, 1]"


class TestSemanticSearch:
    """
    T043: Integration test for US3 (semantic search)
    Verify that semantic search finds conceptually related documents
    """

    def test_synonym_queries_find_related_docs(self, search_engine):
        """Test that synonym queries find overlapping results"""
        synonym_pairs = [
            ("query tracking", "RAG monitoring"),
            ("AI workers", "specialized agents"),
            ("code search", "git history"),
        ]

        for query1, query2 in synonym_pairs:
            results1 = search_engine.search(query=query1, limit=5, mode="hybrid")
            results2 = search_engine.search(query=query2, limit=5, mode="hybrid")

            # Should both return results
            assert len(results1) > 0, f"No results for '{query1}'"
            assert len(results2) > 0, f"No results for '{query2}'"

            # Check for conceptual overlap (at least one shared doc ID OR similar high scores)
            docs1 = {r.document.id for r in results1}
            docs2 = {r.document.id for r in results2}
            overlap = docs1 & docs2

            # Either direct overlap or both queries score highly (indicating similar semantic space)
            has_overlap = len(overlap) > 0
            both_high_scores = results1[0].score >= 0.6 and results2[0].score >= 0.6

            assert has_overlap or both_high_scores, \
                f"Synonyms '{query1}' and '{query2}' found no semantic relationship"

    def test_semantic_mode_vs_keyword_mode(self, search_engine):
        """Test that semantic mode finds different results than keyword mode"""
        query = "intelligent automation system"

        semantic_results = search_engine.search(query=query, limit=5, mode="semantic")
        keyword_results = search_engine.search(query=query, limit=5, mode="bm25")

        # Both should return results
        assert len(semantic_results) > 0, "Semantic mode returned no results"
        assert len(keyword_results) > 0, "Keyword mode returned no results"

        # Semantic scores should generally be higher for this conceptual query
        semantic_top_score = semantic_results[0].score
        keyword_top_score = keyword_results[0].score

        # Semantic search should excel at conceptual queries
        assert semantic_top_score >= keyword_top_score * 0.8, \
            f"Semantic score {semantic_top_score:.4f} much lower than keyword {keyword_top_score:.4f}"

    def test_query_expansion_improves_results(self, search_engine):
        """Test that query expansion finds additional relevant results"""
        # Query with expandable term
        query_with_expansion = "python ml"  # "ml" should expand to "machine learning"

        # Search
        results = search_engine.search(query=query_with_expansion, limit=10, mode="hybrid")

        # Should find results related to both python and machine learning
        assert len(results) >= 5, "Query expansion didn't return sufficient results"

        # Check expanded terms
        expanded = search_engine.expand_query(query_with_expansion)
        assert "machine learning" in " ".join(expanded.expanded).lower(), \
            "Query expansion didn't expand 'ml' to 'machine learning'"


class TestHybridSearchConfiguration:
    """
    Test the hybrid search configuration (95% semantic, 5% keyword)
    """

    def test_hybrid_weight_configuration(self, search_engine):
        """Test that hybrid weight is set to 0.95"""
        assert search_engine._hybrid_weight == 0.95, \
            f"Expected hybrid_weight=0.95, got {search_engine._hybrid_weight}"

    def test_hybrid_mode_balances_semantic_and_keyword(self, search_engine):
        """Test that hybrid mode combines semantic and keyword appropriately"""
        # Query that would score differently in semantic vs keyword
        query = "AI agent system"

        hybrid_results = search_engine.search(query=query, limit=5, mode="hybrid")
        semantic_results = search_engine.search(query=query, limit=5, mode="semantic")

        # Hybrid should return results
        assert len(hybrid_results) > 0, "Hybrid mode returned no results"

        # Hybrid top score should be close to semantic (since 95% semantic weight)
        if len(semantic_results) > 0:
            hybrid_top = hybrid_results[0].score
            semantic_top = semantic_results[0].score

            # Should be within 10% of semantic score (since 95% weight)
            ratio = hybrid_top / semantic_top if semantic_top > 0 else 0
            assert ratio >= 0.85, \
                f"Hybrid score {hybrid_top:.4f} too far from semantic {semantic_top:.4f} (ratio: {ratio:.2f})"
