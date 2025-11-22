"""
Stub implementation of DocumentProcessorPort.

Provides simple text extraction and chunking for testing without
requiring real file format parsers.
"""

from pathlib import Path

from memoria.domain.entities import Chunk, Document


class DocumentProcessorStub:
    """
    Stub document processor that handles plain text files.

    Provides basic text extraction and chunking functionality
    sufficient for testing application layer logic.
    """

    def __init__(self) -> None:
        """Initialize stub processor."""
        self._supported_formats = ["txt", "md"]

    def extract_text(self, file_path: Path) -> str:
        """
        Extract text from a plain text file.

        Args:
            file_path: Path to file

        Returns:
            Extracted text content

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format not supported
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check if format is supported
        extension = file_path.suffix.lstrip(".")
        if extension not in self._supported_formats:
            raise ValueError(
                f"Unsupported format: {extension}. Supported: {self._supported_formats}"
            )

        # Read plain text
        return file_path.read_text(encoding="utf-8")

    def chunk_text(self, text: str, chunk_size: int, overlap: int = 0) -> list[Chunk]:
        """
        Split text into chunks using simple character-based splitting.

        This is a naive implementation that doesn't respect sentence boundaries.
        Real implementations would use smarter chunking (sentence-aware, etc.).

        Args:
            text: Text to chunk
            chunk_size: Target size of each chunk in characters
            overlap: Number of characters to overlap between chunks

        Returns:
            List of text chunks with position information
        """
        if not text:
            raise ValueError("Text cannot be empty")
        if chunk_size < 1:
            raise ValueError(f"Chunk size must be positive, got {chunk_size}")
        if overlap < 0:
            raise ValueError(f"Overlap must be non-negative, got {overlap}")
        if overlap >= chunk_size:
            raise ValueError(f"Overlap ({overlap}) must be less than chunk_size ({chunk_size})")

        chunks: list[Chunk] = []
        start = 0
        chunk_id = 0

        while start < len(text):
            # Calculate end position for this chunk
            end = min(start + chunk_size, len(text))

            # Try to break at word boundary if not at end of text
            if end < len(text) and not text[end].isspace():
                # Look backwards for a space
                space_pos = text.rfind(" ", start, end)
                if space_pos > start:  # Found a space
                    end = space_pos

            chunk_text = text[start:end].strip()
            if chunk_text:  # Only add non-empty chunks
                chunk = Chunk(
                    text=chunk_text,
                    start_pos=start,
                    end_pos=end,
                    metadata={"chunk_id": str(chunk_id)},
                )
                chunks.append(chunk)
                chunk_id += 1

            # Move to next chunk start (with overlap)
            # Ensure we always advance forward to avoid infinite loops
            next_start = end - overlap
            if next_start <= start:
                # If overlap is too large, just advance by 1
                next_start = start + 1
            start = next_start
            if start >= len(text):
                break

        return chunks

    def process_document(
        self, file_path: Path, chunk_size: int = 1000, overlap: int = 100
    ) -> list[Document]:
        """
        Process a document into chunks ready for indexing.

        Args:
            file_path: Path to document to process
            chunk_size: Target size of each chunk
            overlap: Overlap between chunks

        Returns:
            List of document chunks with metadata
        """
        # Extract text
        text = self.extract_text(file_path)

        # Chunk text
        chunks = self.chunk_text(text, chunk_size=chunk_size, overlap=overlap)

        # Convert chunks to documents
        documents: list[Document] = []
        for chunk in chunks:
            doc = Document(
                id=f"{file_path.stem}_{chunk.metadata['chunk_id']}",
                content=chunk.text,
                metadata={
                    "source_file": str(file_path),
                    "chunk_id": chunk.metadata["chunk_id"],
                    "start_pos": str(chunk.start_pos),
                    "end_pos": str(chunk.end_pos),
                    "file_type": file_path.suffix.lstrip("."),
                },
                embedding=None,  # Embedding will be added by embedding generator
            )
            documents.append(doc)

        return documents

    def supported_formats(self) -> list[str]:
        """Get list of supported file formats."""
        return self._supported_formats
