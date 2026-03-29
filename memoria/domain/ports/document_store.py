"""
DocumentStorePort - Protocol for durable document storage.

This port defines the contract for storing and retrieving full document
content with metadata. Postgres is the production implementation;
DocumentStoreStub provides an in-memory implementation for tests.
"""

from typing import Iterator, Protocol

from ..entities import StoredDocument


class DocumentStorePort(Protocol):
    """
    Port for durable document storage.

    Stores full document content (not chunks) as the single source of truth.
    ChromaDB stores only derived chunks/embeddings.
    """

    def store(self, source_id: str, title: str, content: str) -> StoredDocument:
        """
        Insert or update a document by source_id.

        If source_id already exists and content fingerprint is unchanged,
        returns the existing record without writing. If fingerprint changed,
        increments version and updates content.

        Args:
            source_id: Stable identifier (e.g. "docs/my-guide.md")
            title: Human-readable title
            content: Full document text

        Returns:
            StoredDocument with current state (including version and timestamps)
        """
        ...

    def get(self, source_id: str) -> StoredDocument | None:
        """
        Retrieve a document by source_id.

        Returns:
            StoredDocument if found, None if not found or soft-deleted
        """
        ...

    def list_all(self) -> list[StoredDocument]:
        """
        Return all active documents (metadata only — content may be omitted for efficiency).

        Returns:
            List of StoredDocument records ordered by source_id
        """
        ...

    def delete(self, source_id: str) -> bool:
        """
        Soft-delete a document by source_id.

        Returns:
            True if document was found and deleted, False if not found
        """
        ...

    def get_fingerprint(self, source_id: str) -> str | None:
        """
        Return the SHA-256 fingerprint of a stored document.

        Fast path for change detection — avoids fetching full content.

        Returns:
            64-char hex fingerprint, or None if document not found
        """
        ...

    def export_all(self) -> Iterator[StoredDocument]:
        """
        Stream all active documents with full content.

        Memory-efficient — yields one document at a time.

        Returns:
            Iterator of StoredDocument records with content populated
        """
        ...

    def count(self) -> int:
        """Return count of active documents."""
        ...

    def health_check(self) -> bool:
        """Return True if store is reachable and operational."""
        ...
