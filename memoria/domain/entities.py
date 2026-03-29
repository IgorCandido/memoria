"""
Domain entities - Core business objects with identity.

All entities are immutable (frozen dataclasses) to prevent accidental mutation
and ensure thread safety.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Document:
    """
    A document in the RAG system.

    Represents a single document with content, metadata, and optional embedding.
    Documents are uniquely identified by their id.
    """

    id: str
    content: str
    metadata: dict[str, str]
    embedding: Optional[list[float]] = None

    def __post_init__(self) -> None:
        """Validate document invariants."""
        if not self.id:
            raise ValueError("Document id cannot be empty")
        if not self.content:
            raise ValueError("Document content cannot be empty")
        if self.embedding is not None and len(self.embedding) == 0:
            raise ValueError("Embedding must be None or non-empty list")


@dataclass(frozen=True)
class SearchResult:
    """
    A search result matching a query.

    Combines a document with its relevance score and rank in the result set.
    """

    document: Document
    score: float
    rank: int

    def __post_init__(self) -> None:
        """Validate search result invariants."""
        if self.score < 0.0 or self.score > 1.0:
            raise ValueError(f"Score must be in [0.0, 1.0], got {self.score}")
        if self.rank < 0:
            raise ValueError(f"Rank must be non-negative, got {self.rank}")


@dataclass(frozen=True)
class Chunk:
    """
    A text chunk extracted from a document.

    Represents a contiguous piece of text with position information
    for reconstruction and attribution.
    """

    text: str
    start_pos: int
    end_pos: int
    metadata: dict[str, str]

    def __post_init__(self) -> None:
        """Validate chunk invariants."""
        if not self.text:
            raise ValueError("Chunk text cannot be empty")
        if self.start_pos < 0:
            raise ValueError(f"Start position must be non-negative, got {self.start_pos}")
        if self.end_pos <= self.start_pos:
            raise ValueError(
                f"End position ({self.end_pos}) must be greater than start ({self.start_pos})"
            )

    @property
    def length(self) -> int:
        """Return the length of the chunk in characters."""
        return self.end_pos - self.start_pos

    def overlaps(self, other: "Chunk") -> bool:
        """Check if this chunk overlaps with another chunk."""
        return not (self.end_pos <= other.start_pos or self.start_pos >= other.end_pos)


class ProgressTracker:
    """
    Tracks progress of long-running indexing operations.

    Mutable by design - tracks state changes during indexing.
    Not a frozen dataclass since it needs to update progress counters.
    """

    def __init__(self, total_documents: int) -> None:
        if total_documents < 0:
            raise ValueError(f"Total documents must be non-negative, got {total_documents}")
        self.total_documents = total_documents
        self.processed_documents = 0
        self.failed_documents = 0
        self.failed_files: list[tuple[str, str]] = []  # (filename, error_message)
        self.current_document = ""
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None

    @property
    def is_complete(self) -> bool:
        return (self.processed_documents + self.failed_documents) >= self.total_documents

    @property
    def success_count(self) -> int:
        return self.processed_documents - self.failed_documents

    @property
    def elapsed_seconds(self) -> float:
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def docs_per_minute(self) -> float:
        elapsed = self.elapsed_seconds
        if elapsed < 0.001:
            return 0.0
        return (self.processed_documents / elapsed) * 60.0

    def mark_processed(self, filename: str) -> None:
        self.processed_documents += 1
        self.current_document = filename

    def mark_failed(self, filename: str, error: str) -> None:
        self.processed_documents += 1
        self.failed_documents += 1
        self.failed_files.append((filename, error))
        self.current_document = filename

    def finish(self) -> None:
        self.end_time = datetime.now()


@dataclass(frozen=True)
class StoredDocument:
    """
    Full document record in the Postgres document store.

    Single source of truth for document content and metadata.
    ChromaDB stores only the derived chunks/embeddings.
    """

    source_id: str
    title: str
    content: str
    fingerprint: str  # SHA-256 hex of strip(content)
    version: int
    created_at: datetime
    updated_at: datetime
    id: str = ""  # UUID from Postgres (empty before first persist)

    def __post_init__(self) -> None:
        """Validate stored document invariants."""
        if not self.source_id or not self.source_id.strip():
            raise ValueError("source_id cannot be empty")
        if not self.title:
            raise ValueError("title cannot be empty")
        if not self.content:
            raise ValueError("content cannot be empty")
        if not self.fingerprint or len(self.fingerprint) != 64:
            raise ValueError("fingerprint must be a 64-char SHA-256 hex string")
        if self.version < 1:
            raise ValueError(f"version must be >= 1, got {self.version}")
        if self.created_at > self.updated_at:
            raise ValueError("created_at cannot be after updated_at")


@dataclass(frozen=True)
class ExportManifest:
    """
    Metadata header written as the first line of an export file.
    """

    exported_at: datetime
    document_count: int
    system_version: str
    format_version: str

    def __post_init__(self) -> None:
        if self.document_count < 0:
            raise ValueError(f"document_count must be non-negative, got {self.document_count}")
        if not self.format_version:
            raise ValueError("format_version cannot be empty")


@dataclass(frozen=True)
class ImportResult:
    """
    Summary of a corpus import operation.
    """

    documents_added: int
    documents_updated: int
    documents_skipped: int
    documents_failed: int
    errors: tuple[tuple[str, str], ...]  # ((source_id, error_message), ...)
    duration_seconds: float

    def __post_init__(self) -> None:
        if self.documents_added < 0:
            raise ValueError("documents_added must be non-negative")
        if self.documents_failed < 0:
            raise ValueError("documents_failed must be non-negative")
        if self.duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")

    @property
    def total_processed(self) -> int:
        return self.documents_added + self.documents_updated + self.documents_skipped + self.documents_failed


@dataclass(frozen=True)
class ReindexResult:
    """
    Summary of a corpus reindex operation.
    """

    documents_processed: int
    chunks_created: int
    documents_failed: int
    errors: tuple[tuple[str, str], ...]  # ((source_id, error_message), ...)
    duration_seconds: float
    embedding_model: str

    def __post_init__(self) -> None:
        if self.documents_processed < 0:
            raise ValueError("documents_processed must be non-negative")
        if self.chunks_created < 0:
            raise ValueError("chunks_created must be non-negative")
        if self.duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")
        if not self.embedding_model:
            raise ValueError("embedding_model cannot be empty")
