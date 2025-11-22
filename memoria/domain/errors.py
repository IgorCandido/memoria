"""
Domain error types for the memoria RAG system.

These errors represent domain-level failures and are raised by adapters
to communicate specific failure modes. They form a protocol that allows
the application layer to handle errors appropriately.

All domain errors are explicit and specific - no generic exceptions.
"""


class MemoriaError(Exception):
    """Base exception for all memoria domain errors."""

    pass


# ============================================================================
# Database Lifecycle Errors
# ============================================================================


class DatabaseNotBuiltError(MemoriaError):
    """
    Raised when attempting operations on an uninitialized database.

    This is a domain-level error indicating the user forgot to call build()
    before attempting search or stats operations.

    Example:
        >>> rag = UniversalRAG(...)
        >>> rag.search("query")  # Without calling build()
        DatabaseNotBuiltError: Database not built. Call build() first.
    """

    def __init__(self, message: str = "Database not built. Call build() first."):
        super().__init__(message)


class DatabaseCorruptedError(MemoriaError):
    """
    Raised when the database exists but is corrupted or unreadable.

    Indicates the database directory/files exist but cannot be opened
    or read properly. Typically requires rebuilding.
    """

    pass


# ============================================================================
# Document Processing Errors
# ============================================================================


class DocumentNotFoundError(MemoriaError):
    """
    Raised when a requested document doesn't exist.

    Used during build() when a specified file path doesn't exist,
    or during document management operations.
    """

    pass


class UnsupportedFormatError(MemoriaError):
    """
    Raised when attempting to process an unsupported file format.

    Example:
        >>> processor.extract_text(Path("file.xyz"))
        UnsupportedFormatError: Unsupported file format: .xyz
    """

    pass


class DocumentExtractionError(MemoriaError):
    """
    Raised when text extraction from a document fails.

    This could be due to:
    - Corrupted PDF/DOCX files
    - Password-protected files
    - Encoding issues
    - Missing dependencies (PyPDF2, python-docx)
    """

    pass


# ============================================================================
# Search Errors
# ============================================================================


class SearchError(MemoriaError):
    """
    Base class for search-related errors.

    Subclasses indicate specific search failure modes.
    """

    pass


class EmptyQueryError(SearchError):
    """
    Raised when search is called with empty query string.

    Example:
        >>> rag.search("")
        EmptyQueryError: Query cannot be empty
    """

    pass


class EmbeddingGenerationError(SearchError):
    """
    Raised when query embedding generation fails.

    Could indicate:
    - Model loading failure
    - Out of memory
    - Invalid input text
    """

    pass


# ============================================================================
# Vector Store Errors
# ============================================================================


class VectorStoreError(MemoriaError):
    """
    Base class for vector store adapter errors.

    Subclasses indicate specific vector store failure modes.
    """

    pass


class VectorStoreConnectionError(VectorStoreError):
    """
    Raised when connection to vector store fails.

    Only relevant for HTTP-based vector stores (ChromaDB HTTP mode).
    """

    pass


class VectorStoreQueryError(VectorStoreError):
    """
    Raised when a vector store query operation fails.

    Could indicate:
    - Invalid query parameters
    - Database corruption
    - Internal vector store error
    """

    pass


class CollectionNotFoundError(VectorStoreError):
    """
    Raised when requested collection doesn't exist.

    Only raised if vector store operations are attempted before
    collection creation.
    """

    pass


# ============================================================================
# Embedding Errors
# ============================================================================


class EmbeddingError(MemoriaError):
    """
    Base class for embedding generation errors.

    Subclasses indicate specific embedding failure modes.
    """

    pass


class ModelLoadError(EmbeddingError):
    """
    Raised when embedding model fails to load.

    Could indicate:
    - Model not found in sentence-transformers cache
    - Network error downloading model
    - Out of memory
    """

    pass


class TextTooLongError(EmbeddingError):
    """
    Raised when input text exceeds model's maximum length.

    Different models have different max token limits.
    Text should be chunked before embedding.
    """

    pass
