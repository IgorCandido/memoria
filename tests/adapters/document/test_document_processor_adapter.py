"""
Tests for DocumentProcessorAdapter.

Inherits from DocumentProcessorPortTests to ensure full port compliance.
"""

import tempfile
from pathlib import Path

import pytest

from memoria.adapters.document.document_processor_adapter import DocumentProcessorAdapter
from memoria.domain.ports.document_processor import DocumentProcessorPort
from tests.ports.test_document_processor_port import DocumentProcessorPortTests


class TestDocumentProcessorAdapter(DocumentProcessorPortTests):
    """
    Test DocumentProcessorAdapter against DocumentProcessorPort contract.

    Inherits all port tests from DocumentProcessorPortTests.
    """

    def create_processor(self) -> DocumentProcessorPort:
        """
        Factory method to create a DocumentProcessorAdapter instance.

        Required by DocumentProcessorPortTests base class.
        """
        return DocumentProcessorAdapter(
            chunk_size=1000,
            chunk_overlap=200,
        )

    def test_supported_formats_includes_basics(self) -> None:
        """Test that supported formats includes at least txt and md."""
        processor = self.create_processor()
        formats = processor.supported_formats()

        # These should always be supported
        assert ".txt" in formats
        assert ".md" in formats

    def test_extract_text_from_markdown(self) -> None:
        """Test markdown file extraction."""
        processor = self.create_processor()

        # Create a test markdown file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Heading\n\nSome **bold** text.\n")
            temp_path = Path(f.name)

        try:
            text = processor.extract_text(temp_path)
            assert "Heading" in text
            assert "bold" in text
        finally:
            temp_path.unlink()

    def test_process_document_creates_metadata(self) -> None:
        """Test that process_document creates proper metadata."""
        processor = self.create_processor()

        # Create test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content " * 200)  # Enough for multiple chunks
            temp_path = Path(f.name)

        try:
            documents = processor.process_document(temp_path)

            assert len(documents) > 0

            # Check metadata
            for doc in documents:
                assert "source" in doc.metadata
                assert "chunk_index" in doc.metadata
                assert "total_chunks" in doc.metadata
                assert doc.metadata["total_chunks"] == len(documents)
        finally:
            temp_path.unlink()
