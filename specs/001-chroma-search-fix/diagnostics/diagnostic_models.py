"""
Diagnostic Data Models for ChromaDB Search Quality Investigation

Feature: 001-chroma-search-fix
Purpose: Define data structures for diagnostic tools and investigation
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class QueryDiagnostic:
    """Diagnostic information about a search query"""
    query_text: str
    query_embedding: list[float]
    embedding_norm: float
    embedding_dim: int
    timestamp: datetime


@dataclass(frozen=True)
class SearchDiagnostic:
    """Diagnostic information about search results"""
    query: QueryDiagnostic
    num_results: int
    raw_distances: list[float]
    similarity_scores: list[float]
    result_ids: list[str]
    execution_time_ms: float
    search_mode: str
    chromadb_query_time_ms: float
    score_range: float

    def __post_init__(self):
        # Validate invariants
        assert len(self.raw_distances) == self.num_results, "raw_distances length mismatch"
        assert len(self.similarity_scores) == self.num_results, "similarity_scores length mismatch"
        assert len(self.result_ids) == self.num_results, "result_ids length mismatch"
        assert all(0.0 <= score <= 1.0 for score in self.similarity_scores), "scores out of [0,1] range"
        assert self.score_range >= 0.0, "score_range must be non-negative"


@dataclass(frozen=True)
class CollectionHealth:
    """Health metrics for ChromaDB collection"""
    collection_name: str
    total_documents: int
    embedding_dimensions: int
    distance_metric: str
    sample_embedding_norms: list[float]
    avg_embedding_norm: float
    std_embedding_norm: float
    vector_space_density: float
    degenerate_vectors_count: int
    index_type: str
    timestamp: datetime

    def is_healthy(self) -> bool:
        """Check if collection meets health criteria"""
        return (
            abs(self.avg_embedding_norm - 1.0) < 0.1 and  # Normalized vectors
            self.std_embedding_norm < 0.1 and  # Consistent normalization
            self.degenerate_vectors_count == 0  # No corrupt data
        )

    def get_health_status(self) -> str:
        """Get human-readable health status"""
        issues = []

        if abs(self.avg_embedding_norm - 1.0) >= 0.1:
            issues.append(f"❌ Embeddings not normalized (avg norm: {self.avg_embedding_norm:.4f})")
        else:
            issues.append(f"✅ Embeddings normalized (avg norm: {self.avg_embedding_norm:.4f})")

        if self.std_embedding_norm >= 0.1:
            issues.append(f"⚠️ Inconsistent normalization (std: {self.std_embedding_norm:.4f})")
        else:
            issues.append(f"✅ Consistent normalization (std: {self.std_embedding_norm:.4f})")

        if self.degenerate_vectors_count > 0:
            issues.append(f"❌ Found {self.degenerate_vectors_count} degenerate vectors")
        else:
            issues.append(f"✅ No degenerate vectors")

        if self.vector_space_density > 0.8:
            issues.append(f"⚠️ Vector space may be collapsed (density: {self.vector_space_density:.4f})")

        return "\n".join(issues)


@dataclass(frozen=True)
class TestQueryResult:
    """Single test query with expected vs actual behavior"""
    query_text: str
    expected_result_count_min: int
    expected_result_count_max: int
    expected_score_min: float
    actual_result_count: int
    actual_top_score: float
    actual_score_range: float
    passes_criteria: bool
    failure_reason: Optional[str] = None

    def get_status_summary(self) -> str:
        """Get human-readable status summary"""
        status = "✅ PASS" if self.passes_criteria else "❌ FAIL"
        summary = [
            f"{status} - '{self.query_text}'",
            f"  Results: {self.actual_result_count} (expected {self.expected_result_count_min}-{self.expected_result_count_max})",
            f"  Top Score: {self.actual_top_score:.2f} (expected ≥{self.expected_score_min:.2f})",
            f"  Score Range: {self.actual_score_range:.2f}"
        ]

        if self.failure_reason:
            summary.append(f"  Reason: {self.failure_reason}")

        return "\n".join(summary)


# Helper functions for creating diagnostic data

def create_query_diagnostic(query_text: str, embedding: list[float]) -> QueryDiagnostic:
    """Create QueryDiagnostic from query text and embedding"""
    import math

    norm = math.sqrt(sum(x * x for x in embedding))

    return QueryDiagnostic(
        query_text=query_text,
        query_embedding=embedding,
        embedding_norm=norm,
        embedding_dim=len(embedding),
        timestamp=datetime.now()
    )


def create_search_diagnostic(
    query: QueryDiagnostic,
    results: dict,
    execution_time_ms: float,
    search_mode: str,
    chromadb_query_time_ms: float
) -> SearchDiagnostic:
    """Create SearchDiagnostic from query and ChromaDB results"""

    num_results = len(results.get('ids', [[]])[0])
    raw_distances = results.get('distances', [[]])[0]

    # Convert distances to similarity scores (assuming cosine distance)
    similarity_scores = [max(0.0, min(1.0, 1.0 - (d / 2.0))) for d in raw_distances]

    score_range = max(similarity_scores) - min(similarity_scores) if similarity_scores else 0.0

    return SearchDiagnostic(
        query=query,
        num_results=num_results,
        raw_distances=list(raw_distances),
        similarity_scores=similarity_scores,
        result_ids=results.get('ids', [[]])[0],
        execution_time_ms=execution_time_ms,
        search_mode=search_mode,
        chromadb_query_time_ms=chromadb_query_time_ms,
        score_range=score_range
    )


def create_test_query_result(
    query_text: str,
    expected_min: int,
    expected_max: int,
    expected_score: float,
    diagnostic: SearchDiagnostic
) -> TestQueryResult:
    """Create TestQueryResult from expectations and diagnostic"""

    passes = (
        expected_min <= diagnostic.num_results <= expected_max and
        (diagnostic.similarity_scores[0] if diagnostic.similarity_scores else 0.0) >= expected_score
    )

    failure_reason = None
    if not passes:
        reasons = []
        if diagnostic.num_results < expected_min:
            reasons.append(f"Only {diagnostic.num_results} results (expected {expected_min}-{expected_max})")
        elif diagnostic.num_results > expected_max:
            reasons.append(f"Too many results: {diagnostic.num_results} (expected {expected_min}-{expected_max})")

        top_score = diagnostic.similarity_scores[0] if diagnostic.similarity_scores else 0.0
        if top_score < expected_score:
            reasons.append(f"Top score {top_score:.2f} < {expected_score:.2f}")

        failure_reason = "; ".join(reasons)

    return TestQueryResult(
        query_text=query_text,
        expected_result_count_min=expected_min,
        expected_result_count_max=expected_max,
        expected_score_min=expected_score,
        actual_result_count=diagnostic.num_results,
        actual_top_score=diagnostic.similarity_scores[0] if diagnostic.similarity_scores else 0.0,
        actual_score_range=diagnostic.score_range,
        passes_criteria=passes,
        failure_reason=failure_reason
    )
