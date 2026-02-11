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
