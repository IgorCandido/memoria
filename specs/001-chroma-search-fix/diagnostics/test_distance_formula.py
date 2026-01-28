"""
Distance Formula Test Script - Test distance-to-similarity conversion

Task: T004 - Distance formula audit (HIGHEST PRIORITY)
Purpose: Test distance-to-similarity formula with known vectors
Output: Console report with formula validation
"""

import sys
import math
from pathlib import Path

# Add memoria to Python path
memoria_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(memoria_root))

from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
from memoria.adapters.sentence_transformers.sentence_transformer_adapter import SentenceTransformerAdapter


def cosine_distance(vec_a: list[float], vec_b: list[float]) -> float:
    """Calculate cosine distance between two vectors"""
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(x * x for x in vec_a))
    norm_b = math.sqrt(sum(x * x for x in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 2.0  # Maximum distance for zero vectors

    cosine_sim = dot_product / (norm_a * norm_b)
    # Cosine distance = 1 - cosine_similarity (range [0, 2])
    return 1.0 - cosine_sim


def current_formula(distance: float) -> float:
    """Current distance-to-similarity formula from chromadb_adapter.py:147-148"""
    return max(0.0, min(1.0, 1.0 - (distance / 2.0)))


def test_known_vectors():
    """Test distance formula with known vector pairs"""
    print("🧪 Distance Formula Test - Known Vector Pairs")
    print("=" * 80)

    # Create embedding generator
    embedding_gen = SentenceTransformerAdapter()

    # Test cases with known relationships
    test_cases = [
        {
            'name': 'Identical Text',
            'query': 'claude loop protocol',
            'document': 'claude loop protocol',
            'expected_distance': 0.0,
            'expected_similarity': 1.0,
            'description': 'Identical vectors should have distance ≈ 0, similarity ≈ 1.0'
        },
        {
            'name': 'Highly Related',
            'query': 'claude loop protocol',
            'document': 'RAG query protocol for claude',
            'expected_distance': 0.2,  # Approximate
            'expected_similarity': 0.9,  # High similarity
            'description': 'Highly related concepts should have distance < 0.3, similarity > 0.85'
        },
        {
            'name': 'Moderately Related',
            'query': 'agent catalog',
            'document': 'specialized agent list',
            'expected_distance': 0.5,  # Approximate
            'expected_similarity': 0.75,  # Moderate similarity
            'description': 'Moderately related concepts should have distance ≈ 0.5, similarity ≈ 0.75'
        },
        {
            'name': 'Weakly Related',
            'query': 'claude loop protocol',
            'document': 'docker container management',
            'expected_distance': 1.0,  # Approximate
            'expected_similarity': 0.5,  # Weak similarity
            'description': 'Weakly related concepts should have distance ≈ 1.0, similarity ≈ 0.5'
        },
        {
            'name': 'Unrelated',
            'query': 'claude loop protocol',
            'document': 'quantum physics equations',
            'expected_distance': 1.5,  # Approximate
            'expected_similarity': 0.25,  # Low similarity
            'description': 'Unrelated concepts should have distance > 1.2, similarity < 0.4'
        }
    ]

    print("Current Formula: similarity = 1.0 - (distance / 2.0)")
    print()

    all_passed = True

    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['name']}")
        print(f"  Query: '{test['query']}'")
        print(f"  Document: '{test['document']}'")
        print()

        # Generate embeddings
        query_emb = embedding_gen.embed_text(test['query']).vector
        doc_emb = embedding_gen.embed_text(test['document']).vector

        # Calculate actual distance
        actual_distance = cosine_distance(query_emb, doc_emb)

        # Apply current formula
        actual_similarity = current_formula(actual_distance)

        # Display results
        print(f"  📏 Measured Distance: {actual_distance:.6f}")
        print(f"     (expected ≈ {test['expected_distance']:.1f})")
        print()
        print(f"  🎯 Converted Similarity: {actual_similarity:.6f}")
        print(f"     (expected ≈ {test['expected_similarity']:.1f})")
        print()

        # Check if result is reasonable
        distance_ok = abs(actual_distance - test['expected_distance']) < 0.5
        similarity_ok = abs(actual_similarity - test['expected_similarity']) < 0.3

        if distance_ok and similarity_ok:
            print(f"  ✅ PASS - {test['description']}")
        else:
            print(f"  ❌ FAIL - {test['description']}")
            all_passed = False

            if not distance_ok:
                print(f"     Distance deviation: {abs(actual_distance - test['expected_distance']):.4f}")
            if not similarity_ok:
                print(f"     Similarity deviation: {abs(actual_similarity - test['expected_similarity']):.4f}")

        print()
        print("-" * 80)
        print()

    # Summary
    print("=" * 80)
    print("📊 Formula Validation Summary")
    print("=" * 80)

    if all_passed:
        print("✅ All tests PASSED - Formula appears correct for known vector pairs")
    else:
        print("❌ Some tests FAILED - Formula may need adjustment")

    print()
    print("🔍 Next Steps:")
    print("  1. If tests pass: Distance formula likely correct, investigate other hypotheses")
    print("  2. If tests fail: Review formula and ChromaDB distance metric configuration")
    print("  3. Check ChromaDB metadata: Does it return cosine distance or cosine similarity?")
    print()

    return all_passed


def test_chromadb_direct():
    """Test ChromaDB distance values directly"""
    print()
    print("🔍 Direct ChromaDB Distance Test")
    print("=" * 80)

    try:
        # Initialize ChromaDB
        adapter = ChromaDBAdapter(collection_name="memoria", use_http=True, http_host="localhost", http_port=8001)
        embedding_gen = SentenceTransformerAdapter()

        # Generate test query embedding
        test_query = "claude loop protocol"
        query_emb = embedding_gen.embed_text(test_query).vector

        print(f"Test Query: '{test_query}'")
        print()

        # Query ChromaDB directly
        results = adapter._collection.query(
            query_embeddings=[query_emb],
            n_results=5,
            include=['distances', 'documents']
        )

        distances = results.get('distances', [[]])[0]
        documents = results.get('documents', [[]])[0]

        print(f"ChromaDB returned {len(distances)} results")
        print()
        print("Raw ChromaDB Distances:")
        print()

        for i, (dist, doc) in enumerate(zip(distances, documents), 1):
            similarity = current_formula(dist)
            doc_preview = doc[:60] + "..." if len(doc) > 60 else doc
            print(f"  {i}. Distance: {dist:.6f} → Similarity: {similarity:.6f}")
            print(f"     Document: {doc_preview}")
            print()

        # Analyze distance range
        min_dist = min(distances) if distances else 0
        max_dist = max(distances) if distances else 0
        print(f"Distance Range: [{min_dist:.6f}, {max_dist:.6f}]")

        # Check if distances are in expected [0, 2] range
        if max_dist > 2.0:
            print(f"⚠️ WARNING: Max distance {max_dist:.6f} > 2.0 (unexpected for cosine distance)")
        elif max_dist < 1.0:
            print(f"⚠️ WARNING: Max distance {max_dist:.6f} < 1.0 (low diversity, possible collapsed space)")
        else:
            print(f"✅ Distance range looks normal for cosine distance")

        print()

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 80)
    print("CHROMADB DISTANCE-TO-SIMILARITY FORMULA TEST")
    print("Task T006 - Distance Metric Audit (HIGHEST PRIORITY)")
    print("=" * 80)
    print()

    # Test with known vectors
    formula_ok = test_known_vectors()

    # Test with real ChromaDB
    test_chromadb_direct()

    print()
    print("=" * 80)
    print("🎯 Conclusion")
    print("=" * 80)
    if formula_ok:
        print("Formula validation passed with synthetic vectors.")
        print("Check ChromaDB direct test results to confirm real-world behavior.")
    else:
        print("Formula validation failed - distance-to-similarity conversion may be incorrect.")
        print("Review ChromaDB documentation for correct distance metric interpretation.")
