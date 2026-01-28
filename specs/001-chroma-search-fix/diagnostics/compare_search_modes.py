"""
Search Mode Comparison Script - Compare semantic, keyword, and hybrid search

Task: T005 - Search mode comparison
Purpose: Compare search modes to identify which mode has issues
Output: Console report with side-by-side comparison
"""

import sys
import time
from pathlib import Path

# Add memoria to Python path
memoria_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(memoria_root))

from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
from memoria.adapters.sentence_transformers.sentence_transformer_adapter import SentenceTransformerAdapter
from memoria.adapters.search.search_engine_adapter import SearchEngineAdapter


# Test queries for comparison
TEST_QUERIES = [
    "claude loop protocol",
    "RAG compliance monitoring",
    "agent catalog",
    "specialized agents",
    "git commit search"
]


def compare_search_modes(query: str, limit: int = 10):
    """
    Compare all search modes for a single query

    Args:
        query: Query text
        limit: Number of results to request
    """
    print(f"Query: '{query}'")
    print("=" * 100)

    # Initialize adapters
    vector_store = ChromaDBAdapter(collection_name="memoria", use_http=True, http_host="localhost", http_port=8001)
    embedder = SentenceTransformerAdapter()
    search_engine = SearchEngineAdapter(vector_store, embedder, hybrid_weight=0.7)

    modes = ['semantic', 'hybrid']  # Note: search_engine only supports semantic and hybrid
    results_by_mode = {}

    for mode in modes:
        try:
            start_time = time.perf_counter()
            results = search_engine.search(
                query=query,
                mode=mode,
                limit=limit
            )
            end_time = time.perf_counter()
            execution_time = (end_time - start_time) * 1000

            results_by_mode[mode] = {
                'results': results,
                'time_ms': execution_time,
                'error': None
            }

        except Exception as e:
            results_by_mode[mode] = {
                'results': [],
                'time_ms': 0,
                'error': str(e)
            }

    # Display comparison table
    print(f"{'Mode':<12} | {'Results':<8} | {'Top Score':<10} | {'Score Range':<12} | {'Time (ms)':<10} | {'Status':<10}")
    print("-" * 100)

    for mode in modes:
        data = results_by_mode[mode]

        if data['error']:
            print(f"{mode:<12} | {'ERROR':<8} | {'-':<10} | {'-':<12} | {'-':<10} | {data['error'][:10]}")
            continue

        results = data['results']
        num_results = len(results) if results else 0

        if num_results == 0:
            print(f"{mode:<12} | {num_results:<8} | {'0.0000':<10} | {'0.0000':<12} | {data['time_ms']:<10.1f} | {'NO RESULTS':<10}")
            continue

        scores = [r.score for r in results]
        top_score = scores[0]
        score_range = max(scores) - min(scores) if len(scores) > 1 else 0.0

        status = "✅ OK" if num_results >= 5 and score_range >= 0.3 else "⚠️ ISSUE"

        print(f"{mode:<12} | {num_results:<8} | {top_score:<10.4f} | {score_range:<12.4f} | {data['time_ms']:<10.1f} | {status:<10}")

    print()

    # Show top 3 results for each mode
    print("Top 3 Results by Mode:")
    print()

    for mode in modes:
        data = results_by_mode[mode]
        results = data['results']

        print(f"{mode.upper()} Mode:")
        if data['error']:
            print(f"  ❌ ERROR: {data['error']}")
        elif not results:
            print(f"  ⚠️ No results returned")
        else:
            for i, result in enumerate(results[:3], 1):
                score = result.score
                content = result.document.content[:70] if result.document.content else ''
                print(f"  {i}. Score: {score:.4f} | {content}...")

        print()

    print("-" * 100)
    print()


def run_mode_comparison():
    """Run search mode comparison for all test queries"""
    print("🔍 Search Mode Comparison")
    print("=" * 100)
    print(f"Testing {len(TEST_QUERIES)} queries across 3 search modes")
    print()

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"Test {i}/{len(TEST_QUERIES)}:")
        compare_search_modes(query)

    # Summary analysis
    print("=" * 100)
    print("📊 Analysis Summary")
    print("=" * 100)
    print()
    print("Key Questions to Answer:")
    print("  1. Do all modes return only 1 result, or just one specific mode?")
    print("  2. Which mode has the best score range (closest to 0.4+ range)?")
    print("  3. Is hybrid search properly combining semantic + keyword results?")
    print("  4. Are score ranges compressed across all modes or just hybrid?")
    print()
    print("Expected Behavior:")
    print("  - Semantic: Should return 5-10 results with semantic similarity")
    print("  - BM25 (keyword): Should return 5-10 results matching keywords")
    print("  - Hybrid: Should return 5-10 results combining both (70% semantic, 30% keyword)")
    print()
    print("If All Modes Fail:")
    print("  → Problem is in ChromaDB adapter (distance formula, query params)")
    print()
    print("If Only Hybrid Fails:")
    print("  → Problem is in hybrid search algorithm (search_engine_adapter.py)")
    print()
    print("If Semantic Fails but BM25 Works:")
    print("  → Problem is in semantic search or embeddings")
    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compare ChromaDB search modes")
    parser.add_argument('--query', help='Single query to test (optional)')
    parser.add_argument('--limit', type=int, default=10, help='Number of results to request')
    args = parser.parse_args()

    if args.query:
        # Test single query
        print("🔍 Search Mode Comparison - Single Query")
        print("=" * 100)
        print()
        compare_search_modes(args.query, args.limit)
    else:
        # Test all queries
        run_mode_comparison()
