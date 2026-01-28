"""
Baseline Test Script - Run diverse queries to establish current behavior

Task: T002 - Baseline testing
Purpose: Document exact current behavior with 20 diverse test queries
Output: baseline_results.csv with query results
"""

import sys
import csv
import time
from datetime import datetime
from pathlib import Path

# Add memoria to Python path
memoria_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(memoria_root))

from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
from memoria.adapters.sentence_transformers.sentence_transformer_adapter import SentenceTransformerAdapter
from memoria.adapters.search.search_engine_adapter import SearchEngineAdapter
from diagnostic_models import create_query_diagnostic, create_search_diagnostic


# Test queries covering diverse topics in the RAG system
TEST_QUERIES = [
    # High-relevance queries (should score ≥0.7)
    "claude loop protocol",
    "RAG compliance monitoring",
    "agent catalog",
    "memoria skill usage",
    "MCP tool decision tree",

    # Semantic queries (concept-based)
    "specialized agent workers",
    "query tracking system",
    "task-specific AI assistants",
    "commit search with embeddings",
    "autonomous coding agents",

    # Mixed queries (semantic + keyword)
    "how to use skills",
    "agent communication patterns",
    "ChromaDB integration",
    "git history search",
    "workflow automation",

    # Edge cases
    "docker",  # Short, ambiguous
    "compliance report format daily monitoring",  # Long, multi-concept
    "xyz123notfound",  # No matches expected
    "agent",  # Very broad, many potential matches
    "troubleshooting failed tests",  # Problem-solving query
]


def run_baseline_tests(output_file: str = "baseline_results.csv"):
    """
    Run all test queries and export results to CSV

    Args:
        output_file: CSV filename for results
    """
    print("📊 ChromaDB Baseline Test Suite")
    print("=" * 60)
    print(f"Test Queries: {len(TEST_QUERIES)}")
    print(f"Output File: {output_file}")
    print()

    # Initialize adapters
    vector_store = ChromaDBAdapter(collection_name="memoria", use_http=True, http_host="localhost", http_port=8001)
    embedder = SentenceTransformerAdapter()
    search_engine = SearchEngineAdapter(vector_store, embedder, hybrid_weight=0.7)

    results = []

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"[{i}/{len(TEST_QUERIES)}] Testing: '{query}'")

        try:
            # Time the query
            start_time = time.perf_counter()
            search_results = search_engine.search(
                query=query,
                mode="hybrid",  # Default mode
                limit=10  # Request 10 results to see if we get them
            )
            end_time = time.perf_counter()
            execution_time_ms = (end_time - start_time) * 1000

            # Extract result metrics
            num_results = len(search_results) if search_results else 0
            top_score = search_results[0].score if search_results else 0.0
            scores = [r.score for r in search_results] if search_results else []
            score_range = max(scores) - min(scores) if len(scores) > 1 else 0.0

            print(f"  Results: {num_results}, Top Score: {top_score:.4f}, Range: {score_range:.4f}, Time: {execution_time_ms:.1f}ms")

            # Record result
            results.append({
                'query': query,
                'num_results': num_results,
                'top_score': top_score,
                'score_range': score_range,
                'min_score': min(scores) if scores else 0.0,
                'max_score': max(scores) if scores else 0.0,
                'search_mode': 'hybrid',
                'execution_time_ms': execution_time_ms,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            results.append({
                'query': query,
                'num_results': 0,
                'top_score': 0.0,
                'score_range': 0.0,
                'min_score': 0.0,
                'max_score': 0.0,
                'search_mode': 'hybrid',
                'execution_time_ms': 0.0,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            })

    # Export to CSV
    output_path = Path(__file__).parent / output_file
    with open(output_path, 'w', newline='') as f:
        fieldnames = ['query', 'num_results', 'top_score', 'score_range', 'min_score', 'max_score',
                      'search_mode', 'execution_time_ms', 'timestamp']
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)

    print()
    print("=" * 60)
    print("📈 Summary Statistics")
    print("=" * 60)

    # Calculate summary stats
    total_queries = len(results)
    successful_queries = sum(1 for r in results if r['num_results'] > 0)
    queries_with_5plus = sum(1 for r in results if r['num_results'] >= 5)
    avg_results = sum(r['num_results'] for r in results) / total_queries if total_queries > 0 else 0
    avg_top_score = sum(r['top_score'] for r in results) / total_queries if total_queries > 0 else 0
    avg_score_range = sum(r['score_range'] for r in results) / total_queries if total_queries > 0 else 0
    avg_time = sum(r['execution_time_ms'] for r in results) / total_queries if total_queries > 0 else 0

    print(f"Total Queries: {total_queries}")
    print(f"Successful Queries: {successful_queries} ({successful_queries/total_queries*100:.1f}%)")
    print(f"Queries with 5+ Results: {queries_with_5plus} ({queries_with_5plus/total_queries*100:.1f}%)")
    print(f"Average Results per Query: {avg_results:.2f}")
    print(f"Average Top Score: {avg_top_score:.4f}")
    print(f"Average Score Range: {avg_score_range:.4f}")
    print(f"Average Execution Time: {avg_time:.1f}ms")
    print()
    print(f"✅ Results exported to: {output_path}")

    # Check against success criteria
    print()
    print("🎯 Success Criteria Check (Current Baseline)")
    print("=" * 60)

    sc001_pass = queries_with_5plus / total_queries >= 0.9
    print(f"SC-001: 90% queries return 5+ results")
    print(f"  Status: {'✅ PASS' if sc001_pass else '❌ FAIL'} ({queries_with_5plus/total_queries*100:.1f}% with 5+ results)")

    sc002_pass = avg_score_range >= 0.4
    print(f"SC-002: Score range ≥0.4")
    print(f"  Status: {'✅ PASS' if sc002_pass else '❌ FAIL'} (avg range: {avg_score_range:.4f})")

    high_rel_queries = [r for r in results if r['query'] in TEST_QUERIES[:5]]  # First 5 are high-relevance
    high_rel_scores = [r['top_score'] for r in high_rel_queries if r['top_score'] > 0]
    sc003_pass = all(score >= 0.7 for score in high_rel_scores) if high_rel_scores else False
    print(f"SC-003: High-relevance queries score ≥0.7")
    print(f"  Status: {'✅ PASS' if sc003_pass else '❌ FAIL'} ({len([s for s in high_rel_scores if s >= 0.7])}/{len(high_rel_scores)} queries)")

    sc006_pass = avg_time < 2000
    print(f"SC-006: Query time <2 seconds")
    print(f"  Status: {'✅ PASS' if sc006_pass else '❌ FAIL'} (avg: {avg_time:.1f}ms, p95: TBD)")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run baseline ChromaDB search tests")
    parser.add_argument('--output', default='baseline_results.csv', help='Output CSV file name')
    args = parser.parse_args()

    run_baseline_tests(output_file=args.output)
