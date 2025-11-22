"""Unit tests for domain value objects."""

import pytest

from memoria.domain.value_objects import DocumentMetadata, Embedding, QueryTerms, Score


class TestScore:
    """Tests for Score value object."""

    def test_create_valid_score(self) -> None:
        """Test creating a valid score."""
        score = Score(value=0.75)
        assert score.value == 0.75
        assert float(score) == 0.75

    def test_score_below_zero_raises_error(self) -> None:
        """Test that score below 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="Score must be in"):
            Score(value=-0.1)

    def test_score_above_one_raises_error(self) -> None:
        """Test that score above 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="Score must be in"):
            Score(value=1.5)

    def test_score_boundary_values(self) -> None:
        """Test boundary values 0.0 and 1.0."""
        assert Score(value=0.0).value == 0.0
        assert Score(value=1.0).value == 1.0

    def test_score_comparison_operators(self) -> None:
        """Test that scores can be compared."""
        low = Score(value=0.3)
        high = Score(value=0.8)

        assert low < high
        assert low <= high
        assert high > low
        assert high >= low
        assert low <= Score(value=0.3)
        assert high >= Score(value=0.8)

    def test_score_is_immutable(self) -> None:
        """Test that scores are frozen/immutable."""
        score = Score(value=0.5)
        with pytest.raises(AttributeError):
            score.value = 0.9  # type: ignore[misc]


class TestEmbedding:
    """Tests for Embedding value object."""

    def test_create_valid_embedding(self) -> None:
        """Test creating a valid embedding."""
        vector = [0.1, 0.2, 0.3, 0.4]
        emb = Embedding(vector=vector)
        assert emb.vector == vector
        assert emb.dimensions == 4

    def test_embedding_empty_vector_raises_error(self) -> None:
        """Test that empty vector raises ValueError."""
        with pytest.raises(ValueError, match="Embedding vector cannot be empty"):
            Embedding(vector=[])

    def test_embedding_to_list(self) -> None:
        """Test converting embedding to list."""
        vector = [0.1, 0.2, 0.3]
        emb = Embedding(vector=vector)
        result = emb.to_list()
        assert result == vector
        # Ensure it's a copy, not the same reference
        result.append(0.4)
        assert emb.dimensions == 3  # Original unchanged

    def test_embedding_dimensions_property(self) -> None:
        """Test dimensions property."""
        assert Embedding(vector=[1.0]).dimensions == 1
        assert Embedding(vector=[1.0] * 384).dimensions == 384
        assert Embedding(vector=[1.0] * 768).dimensions == 768

    def test_embedding_is_immutable(self) -> None:
        """Test that embeddings are frozen/immutable."""
        emb = Embedding(vector=[0.1, 0.2])
        with pytest.raises(AttributeError):
            emb.vector = [0.3, 0.4]  # type: ignore[misc]


class TestQueryTerms:
    """Tests for QueryTerms value object."""

    def test_create_valid_query_terms(self) -> None:
        """Test creating valid query terms."""
        terms = QueryTerms(original="python", expanded=["python", "programming", "code"])
        assert terms.original == "python"
        assert terms.expanded == ["python", "programming", "code"]

    def test_query_terms_empty_original_raises_error(self) -> None:
        """Test that empty original raises ValueError."""
        with pytest.raises(ValueError, match="Original query cannot be empty"):
            QueryTerms(original="", expanded=["test"])

    def test_query_terms_empty_expanded_raises_error(self) -> None:
        """Test that empty expanded list raises ValueError."""
        with pytest.raises(ValueError, match="Expanded terms cannot be empty"):
            QueryTerms(original="test", expanded=[])

    def test_query_terms_all_terms_property(self) -> None:
        """Test all_terms property."""
        terms = QueryTerms(original="python", expanded=["programming"])
        assert terms.all_terms == ["python", "programming"]

    def test_query_terms_term_count_property(self) -> None:
        """Test term_count property."""
        terms = QueryTerms(original="python", expanded=["programming", "code"])
        assert terms.term_count == 3  # 1 original + 2 expanded

    def test_query_terms_is_immutable(self) -> None:
        """Test that query terms are frozen/immutable."""
        terms = QueryTerms(original="test", expanded=["testing"])
        with pytest.raises(AttributeError):
            terms.original = "modified"  # type: ignore[misc]


class TestDocumentMetadata:
    """Tests for DocumentMetadata value object."""

    def test_create_valid_metadata(self) -> None:
        """Test creating valid metadata."""
        metadata = DocumentMetadata(
            source_file="test.pdf",
            file_type="pdf",
            size_bytes=1024,
            tags=frozenset(["technical", "python"]),
            custom={"author": "John Doe"},
        )
        assert metadata.source_file == "test.pdf"
        assert metadata.file_type == "pdf"
        assert metadata.size_bytes == 1024
        assert "technical" in metadata.tags

    def test_metadata_empty_source_file_raises_error(self) -> None:
        """Test that empty source file raises ValueError."""
        with pytest.raises(ValueError, match="Source file cannot be empty"):
            DocumentMetadata(
                source_file="",
                file_type="pdf",
                size_bytes=100,
                tags=frozenset(),
                custom={},
            )

    def test_metadata_empty_file_type_raises_error(self) -> None:
        """Test that empty file type raises ValueError."""
        with pytest.raises(ValueError, match="File type cannot be empty"):
            DocumentMetadata(
                source_file="test.pdf",
                file_type="",
                size_bytes=100,
                tags=frozenset(),
                custom={},
            )

    def test_metadata_negative_size_raises_error(self) -> None:
        """Test that negative size raises ValueError."""
        with pytest.raises(ValueError, match="Size must be non-negative"):
            DocumentMetadata(
                source_file="test.pdf",
                file_type="pdf",
                size_bytes=-1,
                tags=frozenset(),
                custom={},
            )

    def test_metadata_has_tag(self) -> None:
        """Test has_tag method."""
        metadata = DocumentMetadata(
            source_file="test.pdf",
            file_type="pdf",
            size_bytes=100,
            tags=frozenset(["python", "coding"]),
            custom={},
        )
        assert metadata.has_tag("python")
        assert not metadata.has_tag("java")

    def test_metadata_to_dict(self) -> None:
        """Test conversion to dictionary."""
        metadata = DocumentMetadata(
            source_file="test.pdf",
            file_type="pdf",
            size_bytes=1024,
            tags=frozenset(["python", "coding"]),
            custom={"author": "Jane"},
        )
        result = metadata.to_dict()
        assert result["source_file"] == "test.pdf"
        assert result["file_type"] == "pdf"
        assert result["size_bytes"] == "1024"
        assert result["author"] == "Jane"
        # Tags should be comma-separated sorted
        assert "coding" in result["tags"] and "python" in result["tags"]

    def test_metadata_is_immutable(self) -> None:
        """Test that metadata is frozen/immutable."""
        metadata = DocumentMetadata(
            source_file="test.pdf",
            file_type="pdf",
            size_bytes=100,
            tags=frozenset(),
            custom={},
        )
        with pytest.raises(AttributeError):
            metadata.source_file = "modified.pdf"  # type: ignore[misc]
