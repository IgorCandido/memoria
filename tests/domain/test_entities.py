"""Unit tests for domain entities."""

import pytest

from memoria.domain.entities import Chunk, Document, SearchResult


class TestDocument:
    """Tests for Document entity."""

    def test_create_valid_document(self) -> None:
        """Test creating a valid document."""
        doc = Document(
            id="doc1", content="test content", metadata={"source": "test.txt"}, embedding=None
        )
        assert doc.id == "doc1"
        assert doc.content == "test content"
        assert doc.metadata == {"source": "test.txt"}
        assert doc.embedding is None

    def test_document_with_embedding(self) -> None:
        """Test document with embedding."""
        embedding = [0.1, 0.2, 0.3]
        doc = Document(id="doc1", content="test", metadata={}, embedding=embedding)
        assert doc.embedding == embedding

    def test_document_empty_id_raises_error(self) -> None:
        """Test that empty id raises ValueError."""
        with pytest.raises(ValueError, match="Document id cannot be empty"):
            Document(id="", content="test", metadata={})

    def test_document_empty_content_raises_error(self) -> None:
        """Test that empty content raises ValueError."""
        with pytest.raises(ValueError, match="Document content cannot be empty"):
            Document(id="doc1", content="", metadata={})

    def test_document_empty_embedding_raises_error(self) -> None:
        """Test that empty embedding list raises ValueError."""
        with pytest.raises(ValueError, match="Embedding must be None or non-empty list"):
            Document(id="doc1", content="test", metadata={}, embedding=[])

    def test_document_is_immutable(self) -> None:
        """Test that documents are frozen/immutable."""
        doc = Document(id="doc1", content="test", metadata={})
        with pytest.raises(AttributeError):
            doc.id = "doc2"  # type: ignore[misc]


class TestSearchResult:
    """Tests for SearchResult entity."""

    def test_create_valid_search_result(self) -> None:
        """Test creating a valid search result."""
        doc = Document(id="doc1", content="test", metadata={})
        result = SearchResult(document=doc, score=0.95, rank=0)
        assert result.document == doc
        assert result.score == 0.95
        assert result.rank == 0

    def test_search_result_score_out_of_range_low(self) -> None:
        """Test that score below 0.0 raises ValueError."""
        doc = Document(id="doc1", content="test", metadata={})
        with pytest.raises(ValueError, match="Score must be in"):
            SearchResult(document=doc, score=-0.1, rank=0)

    def test_search_result_score_out_of_range_high(self) -> None:
        """Test that score above 1.0 raises ValueError."""
        doc = Document(id="doc1", content="test", metadata={})
        with pytest.raises(ValueError, match="Score must be in"):
            SearchResult(document=doc, score=1.5, rank=0)

    def test_search_result_negative_rank_raises_error(self) -> None:
        """Test that negative rank raises ValueError."""
        doc = Document(id="doc1", content="test", metadata={})
        with pytest.raises(ValueError, match="Rank must be non-negative"):
            SearchResult(document=doc, score=0.5, rank=-1)

    def test_search_result_is_immutable(self) -> None:
        """Test that search results are frozen/immutable."""
        doc = Document(id="doc1", content="test", metadata={})
        result = SearchResult(document=doc, score=0.5, rank=0)
        with pytest.raises(AttributeError):
            result.score = 0.9  # type: ignore[misc]


class TestChunk:
    """Tests for Chunk entity."""

    def test_create_valid_chunk(self) -> None:
        """Test creating a valid chunk."""
        chunk = Chunk(text="test chunk", start_pos=0, end_pos=10, metadata={})
        assert chunk.text == "test chunk"
        assert chunk.start_pos == 0
        assert chunk.end_pos == 10
        assert chunk.length == 10

    def test_chunk_empty_text_raises_error(self) -> None:
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="Chunk text cannot be empty"):
            Chunk(text="", start_pos=0, end_pos=10, metadata={})

    def test_chunk_negative_start_pos_raises_error(self) -> None:
        """Test that negative start position raises ValueError."""
        with pytest.raises(ValueError, match="Start position must be non-negative"):
            Chunk(text="test", start_pos=-1, end_pos=10, metadata={})

    def test_chunk_end_before_start_raises_error(self) -> None:
        """Test that end position before start raises ValueError."""
        with pytest.raises(ValueError, match="End position .* must be greater than start"):
            Chunk(text="test", start_pos=10, end_pos=5, metadata={})

    def test_chunk_length_property(self) -> None:
        """Test chunk length calculation."""
        chunk = Chunk(text="test", start_pos=100, end_pos=150, metadata={})
        assert chunk.length == 50

    def test_chunk_overlaps_with_another(self) -> None:
        """Test overlap detection between chunks."""
        chunk1 = Chunk(text="test1", start_pos=0, end_pos=10, metadata={})
        chunk2 = Chunk(text="test2", start_pos=5, end_pos=15, metadata={})
        chunk3 = Chunk(text="test3", start_pos=20, end_pos=30, metadata={})

        assert chunk1.overlaps(chunk2)
        assert chunk2.overlaps(chunk1)
        assert not chunk1.overlaps(chunk3)
        assert not chunk3.overlaps(chunk1)

    def test_chunk_is_immutable(self) -> None:
        """Test that chunks are frozen/immutable."""
        chunk = Chunk(text="test", start_pos=0, end_pos=10, metadata={})
        with pytest.raises(AttributeError):
            chunk.text = "modified"  # type: ignore[misc]
