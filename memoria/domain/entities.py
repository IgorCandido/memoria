"""
Domain entities - Core business objects with identity.

All entities are immutable (frozen dataclasses) to prevent accidental mutation
and ensure thread safety.
"""

from dataclasses import dataclass
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
