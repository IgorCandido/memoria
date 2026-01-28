"""
Validation Script - Verify fix meets success criteria

Purpose: Validate that the hybrid search fix resolves score compression
Output: Console report with success/failure for each criterion
"""

import sys
from pathlib import Path

# Add memoria to Python path
memoria_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(memoria_root))

from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
from memoria.adapters.sentence_transformers.sentence_transformer_adapter import SentenceTransformerAdapter
from memoria.adapters.search.search_engine_adapter import SearchEngineAdapter


# Test queries for validation
TEST_QUERIES = [
    "claude loop protocol",
    "RAG compliance monitoring",
    "agent catalog",
    "memoria skill usage",
    "MCP tool decision tree",
    "specialized agent workers",
    "query tracking system",
    "task-specific AI assistants",
    "commit search with embeddings",
    "autonomous coding agents",
]

# High-relevance queries (should score ≥0.7)
HIGH_RELEVANCE_QUERIES = [
    "claude loop protocol",
    "RAG compliance monitoring",
    "agent catalog",
]


def validate_sc001(search_engine):
    """
    SC-001: 90% of queries return 5+ results

    Returns:
        (passed: bool, details: str)
    """
    print("Testing SC-001: 90% queries return 5+ results")
    print("-" * 80)

    queries_with_5plus = 0
    total_queries = len(TEST_QUERIES)

    for query in TEST_QUERIES:
        results = search_engine.search(query=query, limit=10, mode="hybrid")
        num_results = len(results)
        has_5plus = num_results >= 5

        if has_5plus:
            queries_with_5plus += 1
            status = "✅"
        else:
            status = "❌"

        print(f"  {status} '{query}': {num_results} results")

    percentage = (queries_with_5plus / total_queries) * 100
    passed = percentage >= 90.0

    print()
    print(f"Result: {queries_with_5plus}/{total_queries} queries returned 5+ results ({percentage:.1f}%)")
    print(f"Status: {'✅ PASS' if passed else '❌ FAIL'} (need ≥90%)")
    print()

    return passed, f"{percentage:.1f}% queries with 5+ results"


def validate_sc002(search_engine):
    """
    SC-002: Score range ≥0.4

    Returns:
        (passed: bool, details: str)
    """
    print("Testing SC-002: Score range ≥0.4")
    print("-" * 80)

    score_ranges = []

    for query in TEST_QUERIES:
        results = search_engine.search(query=query, limit=10, mode="hybrid")

        if len(results) > 1:
            scores = [r.score for r in results]
            score_range = max(scores) - min(scores)
            score_ranges.append(score_range)
            print(f"  '{query}': range {score_range:.4f} (min={min(scores):.4f}, max={max(scores):.4f})")
        else:
            print(f"  '{query}': SKIP (< 2 results)")

    avg_range = sum(score_ranges) / len(score_ranges) if score_ranges else 0.0
    passed = avg_range >= 0.4

    print()
    print(f"Average Score Range: {avg_range:.4f}")
    print(f"Status: {'✅ PASS' if passed else '❌ FAIL'} (need ≥0.4)")
    print()

    return passed, f"avg range {avg_range:.4f}"


def validate_sc003(search_engine):
    """
    SC-003: High-relevance queries score ≥0.7

    Returns:
        (passed: bool, details: str)
    """
    print("Testing SC-003: High-relevance queries score ≥0.7")
    print("-" * 80)

    high_scoring_count = 0
    total_high_relevance = len(HIGH_RELEVANCE_QUERIES)

    for query in HIGH_RELEVANCE_QUERIES:
        results = search_engine.search(query=query, limit=10, mode="hybrid")

        if results:
            top_score = results[0].score
            is_high = top_score >= 0.7

            if is_high:
                high_scoring_count += 1
                status = "✅"
            else:
                status = "❌"

            print(f"  {status} '{query}': top score {top_score:.4f}")
        else:
            print(f"  ❌ '{query}': NO RESULTS")

    percentage = (high_scoring_count / total_high_relevance) * 100
    passed = high_scoring_count >= (total_high_relevance * 0.8)  # Allow 80% success rate

    print()
    print(f"Result: {high_scoring_count}/{total_high_relevance} queries scored ≥0.7 ({percentage:.1f}%)")
    print(f"Status: {'✅ PASS' if passed else '❌ FAIL'} (need ≥80%)")
    print()

    return passed, f"{percentage:.1f}% high-relevance with ≥0.7 score"


def main():
    """Run all validation tests"""
    print("=" * 80)
    print("MEMORIA FIX VALIDATION - Success Criteria Check")
    print("=" * 80)
    print()

    # Initialize search engine with FIX (hybrid_weight=0.95)
    print("Initializing search engine with FIX (hybrid_weight=0.95)...")
    vector_store = ChromaDBAdapter(
        collection_name="memoria",
        use_http=True,
        http_host="localhost",
        http_port=8001
    )
    embedder = SentenceTransformerAdapter()
    search_engine = SearchEngineAdapter(vector_store, embedder, hybrid_weight=0.95)
    print("✓ Search engine initialized")
    print()

    # Run validation tests
    results = {}

    results["SC-001"] = validate_sc001(search_engine)
    results["SC-002"] = validate_sc002(search_engine)
    results["SC-003"] = validate_sc003(search_engine)

    # Summary
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    all_passed = True
    for criterion, (passed, details) in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{criterion}: {status} - {details}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 ALL SUCCESS CRITERIA MET - FIX VALIDATED!")
    else:
        print("⚠️ SOME CRITERIA FAILED - FURTHER INVESTIGATION NEEDED")
    print()


if __name__ == "__main__":
    main()
