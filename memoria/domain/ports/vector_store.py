"""
VectorStorePort - Protocol for vector database operations.

This port defines the contract for storing and retrieving documents
with vector embeddings. Any vector database (ChromaDB, Pinecone, Weaviate, etc.)
can implement this port.
"""

from typing import Protocol

from ..entities import Document, SearchResult


class VectorStorePort(Protocol):
    """
    Port for vector database operations.

    All methods are synchronous for simplicity. Async variants can be added
    via a separate protocol if needed.
    """

    def add_documents(self, docs: list[Document]) -> None:
        """
        Add documents to the vector store.

        Args:
            docs: List of documents with embeddings to store

        Raises:
            ValueError: If documents are missing embeddings
            ConnectionError: If unable to connect to vector store
        """
        ...

    def search(self, query_embedding: list[float], k: int) -> list[SearchResult]:
        """
        Search for documents similar to the query embedding.

        Args:
            query_embedding: Query vector to search for
            k: Number of results to return

        Returns:
            List of search results, ordered by relevance (highest first)

        Raises:
            ValueError: If k is invalid or embedding is wrong dimension
            ConnectionError: If unable to connect to vector store
        """
        ...

    def get_by_id(self, doc_id: str) -> Document | None:
        """
        Retrieve a document by its ID.

        Args:
            doc_id: Unique document identifier

        Returns:
            Document if found, None otherwise
        """
        ...

    def delete(self, doc_id: str) -> bool:
        """
        Delete a document by its ID.

        Args:
            doc_id: Unique document identifier

        Returns:
            True if document was deleted, False if not found
        """
        ...

    def get_stats(self) -> dict[str, int]:
        """
        Get statistics about the vector store.

        Returns:
            Dictionary with stats like document_count, collection_name, etc.
        """
        ...

    def clear(self) -> None:
        """
        Remove all documents from the vector store.

        Use with caution - this is typically only used in testing.
        """
        ...
