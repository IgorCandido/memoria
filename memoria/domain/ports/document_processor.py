"""
DocumentProcessorPort - Protocol for document processing operations.

This port defines the contract for extracting text from various file formats,
chunking text, and processing documents for indexing.
"""

from pathlib import Path
from typing import Protocol

from ..entities import Chunk, Document


class DocumentProcessorPort(Protocol):
    """
    Port for document processing operations.

    Handles file format extraction, text chunking, and document preparation
    for the RAG system.
    """

    def extract_text(self, file_path: Path) -> str:
        """
        Extract text content from a file.

        Supports various formats: PDF, DOCX, Markdown, plain text, etc.

        Args:
            file_path: Path to file to extract text from

        Returns:
            Extracted text content

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is not supported
            RuntimeError: If extraction fails
        """
        ...

    def chunk_text(self, text: str, chunk_size: int, overlap: int = 0) -> list[Chunk]:
        """
        Split text into chunks for processing.

        Uses smart chunking that respects sentence/paragraph boundaries
        when possible.

        Args:
            text: Text to chunk
            chunk_size: Target size of each chunk in characters
            overlap: Number of characters to overlap between chunks

        Returns:
            List of text chunks with position information

        Raises:
            ValueError: If chunk_size or overlap are invalid
        """
        ...

    def process_document(
        self, file_path: Path, chunk_size: int = 1000, overlap: int = 100
    ) -> list[Document]:
        """
        Process a document into chunks ready for indexing.

        This is a convenience method that combines extract_text and chunk_text.

        Args:
            file_path: Path to document to process
            chunk_size: Target size of each chunk
            overlap: Overlap between chunks

        Returns:
            List of document chunks with metadata

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is not supported or parameters are invalid
            RuntimeError: If processing fails
        """
        ...

    def supported_formats(self) -> list[str]:
        """
        Get list of supported file formats.

        Returns:
            List of file extensions (e.g., ["pdf", "docx", "md", "txt"])
        """
        ...
