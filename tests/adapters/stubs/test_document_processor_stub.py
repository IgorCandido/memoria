"""Test that DocumentProcessorStub passes all DocumentProcessorPortTests."""

from pathlib import Path

from memoria.adapters.stubs.document_processor_stub import DocumentProcessorStub
from memoria.domain.ports.document_processor import DocumentProcessorPort
from tests.ports.test_document_processor_port import DocumentProcessorPortTests


class TestDocumentProcessorStub(DocumentProcessorPortTests):
    """
    Test DocumentProcessorStub implementation.

    By inheriting from DocumentProcessorPortTests, this stub automatically
    runs all 10 port tests to ensure it behaves correctly.
    """

    def create_processor(self) -> DocumentProcessorPort:
        """Create a DocumentProcessorStub instance for testing."""
        return DocumentProcessorStub()

    def create_test_file(self, tmp_path: Path, content: str, extension: str) -> Path:
        """Create a test file with the given content and extension."""
        file_path = tmp_path / f"test.{extension}"
        file_path.write_text(content, encoding="utf-8")
        return file_path
