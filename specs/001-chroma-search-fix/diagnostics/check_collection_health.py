"""
Collection Health Check Script - Analyze ChromaDB collection metadata

Task: T003 - Collection health check
Purpose: Analyze ChromaDB collection metadata and vector space quality
Output: collection_stats.json with health metrics
"""

import sys
import json
import math
from datetime import datetime
from pathlib import Path

# Add memoria to Python path
memoria_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(memoria_root))

from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
from diagnostic_models import CollectionHealth


def calculate_vector_space_density(embeddings: list[list[float]]) -> float:
    """
    Calculate vector space density (how tightly clustered vectors are)

    High density (>0.8) may indicate collapsed vector space

    Returns:
        float: Density metric in [0, 1] range
    """
    if len(embeddings) < 2:
        return 0.0

    # Calculate pairwise cosine similarities
    similarities = []
    sample_size = min(len(embeddings), 100)  # Sample to avoid O(n^2) for large collections

    for i in range(sample_size):
        for j in range(i + 1, sample_size):
            vec_i = embeddings[i]
            vec_j = embeddings[j]

            # Cosine similarity
            dot_product = sum(a * b for a, b in zip(vec_i, vec_j))
            norm_i = math.sqrt(sum(x * x for x in vec_i))
            norm_j = math.sqrt(sum(x * x for x in vec_j))

            if norm_i > 0 and norm_j > 0:
                similarity = dot_product / (norm_i * norm_j)
                similarities.append(abs(similarity))  # Absolute value

    # Density is average similarity
    return sum(similarities) / len(similarities) if similarities else 0.0


def check_degenerate_vectors(embeddings: list[list[float]]) -> int:
    """
    Count degenerate vectors (all zeros, NaN, inf)

    Returns:
        int: Count of degenerate vectors
    """
    count = 0
    for vec in embeddings:
        # Check for all zeros
        if all(x == 0.0 for x in vec):
            count += 1
            continue

        # Check for NaN or inf
        if any(math.isnan(x) or math.isinf(x) for x in vec):
            count += 1
            continue

    return count


def check_collection_health(output_file: str = "collection_stats.json") -> CollectionHealth:
    """
    Analyze ChromaDB collection health and export metrics

    Args:
        output_file: JSON filename for stats export

    Returns:
        CollectionHealth object with metrics
    """
    print("🔍 ChromaDB Collection Health Check")
    print("=" * 60)

    try:
        # Initialize ChromaDB adapter
        adapter = ChromaDBAdapter(
            collection_name="memoria",
            use_http=True,
            http_host="localhost",
            http_port=8001
        )

        # Get collection metadata
        collection = adapter._collection
        total_docs = collection.count()

        print(f"Collection: {collection.name}")
        print(f"Total Documents: {total_docs}")

        if total_docs == 0:
            print("⚠️ WARNING: Collection is empty!")
            return None

        # Sample embeddings for analysis
        sample_size = min(total_docs, 100)
        print(f"Sampling: {sample_size} embeddings for analysis")

        # Get sample embeddings
        sample_results = collection.get(
            limit=sample_size,
            include=["embeddings"]
        )

        embeddings = sample_results.get('embeddings', [])

        if embeddings is None or len(embeddings) == 0:
            print("❌ ERROR: No embeddings found in collection")
            return None

        print(f"Embeddings Retrieved: {len(embeddings)}")

        # Calculate embedding norms
        norms = []
        for emb in embeddings:
            norm = math.sqrt(sum(x * x for x in emb))
            norms.append(norm)

        avg_norm = sum(norms) / len(norms)
        variance = sum((n - avg_norm) ** 2 for n in norms) / len(norms)
        std_norm = math.sqrt(variance)

        # Check for degenerate vectors
        degenerate_count = check_degenerate_vectors(embeddings)

        # Calculate vector space density
        density = calculate_vector_space_density(embeddings)

        # Get collection metadata
        metadata = collection.metadata or {}
        distance_metric = metadata.get('hnsw:space', 'unknown')

        # Create health object
        health = CollectionHealth(
            collection_name=collection.name,
            total_documents=total_docs,
            embedding_dimensions=len(embeddings[0]) if len(embeddings) > 0 else 0,
            distance_metric=distance_metric,
            sample_embedding_norms=norms,
            avg_embedding_norm=avg_norm,
            std_embedding_norm=std_norm,
            vector_space_density=density,
            degenerate_vectors_count=degenerate_count,
            index_type=metadata.get('hnsw:construction_ef', 'unknown'),
            timestamp=datetime.now()
        )

        # Display health metrics
        print()
        print("📊 Health Metrics")
        print("=" * 60)
        print(f"Embedding Dimensions: {health.embedding_dimensions}")
        print(f"Distance Metric: {health.distance_metric}")
        print(f"Average Norm: {health.avg_embedding_norm:.6f}")
        print(f"Std Dev Norm: {health.std_embedding_norm:.6f}")
        print(f"Vector Space Density: {health.vector_space_density:.4f}")
        print(f"Degenerate Vectors: {health.degenerate_vectors_count}")
        print()
        print("🏥 Health Status")
        print("=" * 60)
        print(health.get_health_status())

        # Export to JSON
        output_path = Path(__file__).parent / output_file
        health_dict = {
            'collection_name': health.collection_name,
            'total_documents': health.total_documents,
            'embedding_dimensions': health.embedding_dimensions,
            'distance_metric': health.distance_metric,
            'sample_size': len(norms),
            'embedding_norms': {
                'mean': health.avg_embedding_norm,
                'std': health.std_embedding_norm,
                'min': min(norms),
                'max': max(norms)
            },
            'vector_space_density': health.vector_space_density,
            'degenerate_vectors': health.degenerate_vectors_count,
            'index_type': str(health.index_type),
            'is_healthy': health.is_healthy(),
            'timestamp': health.timestamp.isoformat()
        }

        with open(output_path, 'w') as f:
            json.dump(health_dict, f, indent=2)

        print()
        print(f"✅ Health metrics exported to: {output_path}")

        return health

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check ChromaDB collection health")
    parser.add_argument('--output', default='collection_stats.json', help='Output JSON file name')
    args = parser.parse_args()

    check_collection_health(output_file=args.output)
