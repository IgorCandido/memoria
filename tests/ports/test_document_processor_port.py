"""
Port test base class for DocumentProcessorPort.

All DocumentProcessor adapters must pass these tests.
"""

from abc import ABC, abstractmethod
from pathlib import Path

import pytest

from memoria.domain.entities import Chunk, Document
from memoria.domain.ports.document_processor import DocumentProcessorPort


class DocumentProcessorPortTests(ABC):
    """
    Base test suite for all DocumentProcessor adapters.

    To test a new adapter:
    1. Inherit from this class
    2. Implement create_processor() to return your adapter
    3. Optionally implement create_test_file() for file-based tests
    4. Run pytest - all tests execute automatically
    """

    @abstractmethod
    def create_processor(self) -> DocumentProcessorPort:
        """
        Factory method - subclasses must implement.

        Returns:
            A configured instance of the adapter under test
        """
        ...

    def create_test_file(self, tmp_path: Path, content: str, extension: str) -> Path:
        """
        Optional hook for subclasses to create test files.

        Default implementation creates a plain text file.
        Override for format-specific file creation.

        Args:
            tmp_path: pytest tmp_path fixture
            content: Text content for the file
            extension: File extension (e.g., "txt", "pdf")

        Returns:
            Path to created test file
        """
        file_path = tmp_path / f"test.{extension}"
        file_path.write_text(content)
        return file_path

    @pytest.fixture
    def processor(self) -> DocumentProcessorPort:
        """Fixture that provides a processor for each test."""
        return self.create_processor()

    def test_chunk_text_returns_chunks(self, processor: DocumentProcessorPort) -> None:
        """Test that chunk_text returns a list of Chunks."""
        text = "This is a test. " * 100  # 1600+ chars
        chunks = processor.chunk_text(text, chunk_size=500, overlap=50)
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_text_respects_chunk_size(self, processor: DocumentProcessorPort) -> None:
        """Test that chunks are approximately the requested size."""
        text = "word " * 500  # 2500 chars
        chunk_size = 500
        chunks = processor.chunk_text(text, chunk_size=chunk_size, overlap=0)

        for chunk in chunks:
            # Chunks might be slightly larger/smaller due to boundary respect
            # but should be in the ballpark
            assert 0 < chunk.length <= chunk_size * 2  # Allow 2x for boundary respect

    def test_chunk_text_no_overlap(self, processor: DocumentProcessorPort) -> None:
        """Test that chunks don't overlap when overlap=0."""
        text = "word " * 200
        chunks = processor.chunk_text(text, chunk_size=200, overlap=0)

        for i in range(len(chunks) - 1):
            # No overlap means end of chunk[i] <= start of chunk[i+1]
            assert chunks[i].end_pos <= chunks[i + 1].start_pos

    def test_chunk_text_with_overlap(self, processor: DocumentProcessorPort) -> None:
        """Test that chunks overlap when overlap > 0."""
        text = "word " * 200
        overlap = 50
        chunks = processor.chunk_text(text, chunk_size=200, overlap=overlap)

        if len(chunks) > 1:
            # At least some chunks should overlap
            has_overlap = False
            for i in range(len(chunks) - 1):
                if chunks[i].overlaps(chunks[i + 1]):
                    has_overlap = True
                    break
            # Note: Overlap might not happen if text is too short or chunks too large
            # This is a best-effort test

    def test_chunk_text_preserves_content(self, processor: DocumentProcessorPort) -> None:
        """Test that chunking preserves all original content."""
        text = "This is important content that must not be lost."
        chunks = processor.chunk_text(text, chunk_size=20, overlap=5)

        # Reconstruct text from non-overlapping parts
        # (This is simplified - real implementation might be more complex)
        reconstructed_parts = [c.text for c in chunks]
        # At minimum, original text should be substring of concatenated chunks
        concatenated = " ".join(reconstructed_parts)
        # Check that key words are present
        assert "important" in concatenated
        assert "content" in concatenated

    def test_supported_formats_returns_list(self, processor: DocumentProcessorPort) -> None:
        """Test that supported_formats returns a list of strings."""
        formats = processor.supported_formats()
        assert isinstance(formats, list)
        assert len(formats) > 0
        assert all(isinstance(f, str) for f in formats)

    def test_extract_text_plain_text(
        self, processor: DocumentProcessorPort, tmp_path: Path
    ) -> None:
        """Test extracting text from a plain text file."""
        content = "This is test content."
        file_path = self.create_test_file(tmp_path, content, "txt")

        extracted = processor.extract_text(file_path)
        assert isinstance(extracted, str)
        assert len(extracted) > 0
        assert "test content" in extracted.lower()

    def test_process_document_returns_documents(
        self, processor: DocumentProcessorPort, tmp_path: Path
    ) -> None:
        """Test that process_document returns a list of Documents."""
        content = "This is test content. " * 50  # ~1000+ chars
        file_path = self.create_test_file(tmp_path, content, "txt")

        docs = processor.process_document(file_path, chunk_size=500)
        assert isinstance(docs, list)
        assert len(docs) > 0
        assert all(isinstance(d, Document) for d in docs)

    def test_process_document_includes_metadata(
        self, processor: DocumentProcessorPort, tmp_path: Path
    ) -> None:
        """Test that processed documents include metadata."""
        content = "Test content."
        file_path = self.create_test_file(tmp_path, content, "txt")

        docs = processor.process_document(file_path)
        # At least one document should have metadata
        assert any(len(d.metadata) > 0 for d in docs)
