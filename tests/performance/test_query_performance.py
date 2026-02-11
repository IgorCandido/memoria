"""
Performance tests for query execution.

Validates:
- SC-004: 90% of queries complete in <2 seconds
- Concurrent query handling (10 simultaneous users, <3s each)
- No search quality regression after optimization

Requires: ChromaDB running on localhost:8001 with populated collection.
"""

import time
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed

from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
from memoria.adapters.sentence_transformers.sentence_transformer_adapter import SentenceTransformerAdapter
from memoria.adapters.search.search_engine_adapter import SearchEngineAdapter


@pytest.fixture(scope="module")
def search_engine():
    """Create search engine connected to production ChromaDB."""
    vector_store = ChromaDBAdapter(
        collection_name="memoria",
        use_http=True,
        http_host="localhost",
        http_port=8001,
    )
    embedder = SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")
    engine = SearchEngineAdapter(vector_store, embedder, hybrid_weight=0.95)
    return engine


DIVERSE_QUERIES = [
    "python programming best practices",
    "machine learning model training",
    "docker container management",
    "API endpoint design patterns",
    "database query optimization",
    "git branching strategy",
    "cloud infrastructure setup",
    "testing strategies for microservices",
    "security vulnerability scanning",
    "performance monitoring tools",
    "CI/CD pipeline configuration",
    "kubernetes deployment",
    "error handling patterns",
    "logging and observability",
    "authentication and authorization",
    "data migration strategies",
    "code review best practices",
    "system architecture design",
    "caching strategies",
    "message queue patterns",
    "RAG system design",
    "embedding model selection",
    "ChromaDB configuration",
    "document chunking strategy",
    "hybrid search optimization",
    "batch processing pipeline",
    "memory management techniques",
    "concurrent programming",
    "network protocols",
    "file system operations",
    "regex pattern matching",
    "JSON parsing",
    "HTTP client configuration",
    "environment variable management",
    "dependency injection",
    "factory design pattern",
    "observer pattern implementation",
    "command line tool development",
    "configuration management",
    "task scheduling",
    "webhook integration",
    "rate limiting strategies",
    "connection pooling",
    "load balancing",
    "service discovery",
    "health check endpoints",
    "graceful shutdown",
    "circuit breaker pattern",
    "retry with backoff",
    "distributed tracing",
]


class TestQueryPerformance:
    """SC-004: 90% of queries complete in <2 seconds."""

    def test_query_latency_under_2_seconds(self, search_engine):
        """90% of 50 diverse queries must complete in <2s."""
        latencies = []

        for query in DIVERSE_QUERIES:
            start = time.time()
            results = search_engine.search(query=query, limit=5, mode="hybrid")
            elapsed = time.time() - start
            latencies.append(elapsed)

        # Sort latencies to find P90
        latencies.sort()
        p90_index = int(len(latencies) * 0.9) - 1
        p90_latency = latencies[p90_index]
        p99_latency = latencies[-1]
        mean_latency = sum(latencies) / len(latencies)

        print(f"\nQuery Performance Results:")
        print(f"  Total queries: {len(latencies)}")
        print(f"  Mean latency:  {mean_latency * 1000:.1f}ms")
        print(f"  P90 latency:   {p90_latency * 1000:.1f}ms")
        print(f"  P99 latency:   {p99_latency * 1000:.1f}ms")
        print(f"  Min latency:   {min(latencies) * 1000:.1f}ms")
        print(f"  Max latency:   {max(latencies) * 1000:.1f}ms")

        under_2s = sum(1 for l in latencies if l < 2.0)
        pct_under_2s = under_2s / len(latencies) * 100

        print(f"  Under 2s:      {under_2s}/{len(latencies)} ({pct_under_2s:.1f}%)")

        assert pct_under_2s >= 90, (
            f"SC-004 FAIL: Only {pct_under_2s:.1f}% of queries under 2s (need 90%). "
            f"P90={p90_latency * 1000:.1f}ms"
        )


class TestConcurrentQueries:
    """Test concurrent query performance (10 simultaneous users)."""

    def test_concurrent_queries_under_3_seconds(self, search_engine):
        """10 concurrent queries must each complete in <3s."""
        queries = DIVERSE_QUERIES[:10]

        def run_query(query):
            start = time.time()
            results = search_engine.search(query=query, limit=5, mode="hybrid")
            elapsed = time.time() - start
            return query, elapsed, len(results)

        results_list = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(run_query, q): q for q in queries}
            for future in as_completed(futures):
                results_list.append(future.result())

        print(f"\nConcurrent Query Results (10 users):")
        all_under_3s = True
        for query, elapsed, count in results_list:
            status = "OK" if elapsed < 3.0 else "SLOW"
            if elapsed >= 3.0:
                all_under_3s = False
            print(f"  [{status}] {elapsed * 1000:.1f}ms - {count} results - {query[:40]}...")

        max_latency = max(e for _, e, _ in results_list)
        print(f"  Max concurrent latency: {max_latency * 1000:.1f}ms")

        assert all_under_3s, (
            f"Concurrent query test FAIL: max latency {max_latency * 1000:.1f}ms (need <3000ms)"
        )


class TestSearchQualityRegression:
    """Verify no quality regression after performance optimization."""

    def test_results_return_5_plus(self, search_engine):
        """SC-001: 90% of queries return 5+ results."""
        queries_with_5_plus = 0
        total = 10

        for query in DIVERSE_QUERIES[:total]:
            results = search_engine.search(query=query, limit=10, mode="hybrid")
            if len(results) >= 5:
                queries_with_5_plus += 1

        pct = queries_with_5_plus / total * 100
        print(f"\nQuality Regression Check:")
        print(f"  Queries returning 5+ results: {queries_with_5_plus}/{total} ({pct:.1f}%)")

        assert pct >= 90, f"SC-001 regression: only {pct:.1f}% return 5+ results"

    def test_high_relevance_scores(self, search_engine):
        """SC-003: High-relevance queries score ≥0.7."""
        high_rel_queries = [
            "RAG search ChromaDB",
            "embedding model sentence transformer",
            "document indexing chunking",
        ]
        all_pass = True

        for query in high_rel_queries:
            results = search_engine.search(query=query, limit=5, mode="hybrid")
            if results:
                top_score = results[0].score
                passed = top_score >= 0.7
                status = "PASS" if passed else "FAIL"
                if not passed:
                    all_pass = False
                print(f"  [{status}] {query}: top_score={top_score:.3f}")

        assert all_pass, "SC-003 regression: some high-relevance queries score <0.7"
