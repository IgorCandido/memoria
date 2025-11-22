"""
Domain value objects - Immutable values without identity.

Value objects are compared by their values, not by identity.
They are frozen dataclasses to ensure immutability.
"""

from dataclasses import dataclass
from typing import Literal


SearchMode = Literal["semantic", "bm25", "hybrid"]


@dataclass(frozen=True)
class Score:
    """
    A relevance score for a search result.

    Scores are normalized to [0.0, 1.0] where 1.0 is most relevant.
    """

    value: float

    def __post_init__(self) -> None:
        """Validate score is in valid range."""
        if self.value < 0.0 or self.value > 1.0:
            raise ValueError(f"Score must be in [0.0, 1.0], got {self.value}")

    def __float__(self) -> float:
        """Allow conversion to float."""
        return self.value

    def __lt__(self, other: object) -> bool:
        """Support comparison operators for sorting."""
        if not isinstance(other, Score):
            return NotImplemented
        return self.value < other.value

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Score):
            return NotImplemented
        return self.value <= other.value

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Score):
            return NotImplemented
        return self.value > other.value

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Score):
            return NotImplemented
        return self.value >= other.value


@dataclass(frozen=True)
class Embedding:
    """
    A vector embedding representing semantic meaning of text.

    Embeddings are typically 384 or 768 dimensional float vectors
    produced by transformer models.
    """

    vector: list[float]

    def __post_init__(self) -> None:
        """Validate embedding is non-empty."""
        if not self.vector:
            raise ValueError("Embedding vector cannot be empty")
        if len(self.vector) < 1:
            raise ValueError(f"Embedding must have at least 1 dimension, got {len(self.vector)}")

    @property
    def dimensions(self) -> int:
        """Return the dimensionality of the embedding."""
        return len(self.vector)

    def to_list(self) -> list[float]:
        """Convert embedding to a list (for serialization)."""
        return list(self.vector)  # Return a copy to maintain immutability


@dataclass(frozen=True)
class QueryTerms:
    """
    A set of query terms after processing and expansion.

    Represents the final query terms used for searching, potentially
    after expansion, synonym replacement, or other query preprocessing.
    """

    original: str
    expanded: list[str]

    def __post_init__(self) -> None:
        """Validate query terms."""
        if not self.original:
            raise ValueError("Original query cannot be empty")
        if not self.expanded:
            raise ValueError("Expanded terms cannot be empty")

    @property
    def all_terms(self) -> list[str]:
        """Return all terms (original + expanded)."""
        return [self.original] + self.expanded

    @property
    def term_count(self) -> int:
        """Return total number of terms."""
        return len(self.all_terms)


@dataclass(frozen=True)
class DocumentMetadata:
    """
    Metadata about a document.

    Stores additional information about a document like source file,
    creation date, author, tags, etc.
    """

    source_file: str
    file_type: str
    size_bytes: int
    tags: frozenset[str]
    custom: dict[str, str]

    def __post_init__(self) -> None:
        """Validate metadata."""
        if not self.source_file:
            raise ValueError("Source file cannot be empty")
        if not self.file_type:
            raise ValueError("File type cannot be empty")
        if self.size_bytes < 0:
            raise ValueError(f"Size must be non-negative, got {self.size_bytes}")

    def has_tag(self, tag: str) -> bool:
        """Check if document has a specific tag."""
        return tag in self.tags

    def to_dict(self) -> dict[str, str]:
        """Convert metadata to dictionary for serialization."""
        result: dict[str, str] = {
            "source_file": self.source_file,
            "file_type": self.file_type,
            "size_bytes": str(self.size_bytes),
            "tags": ",".join(sorted(self.tags)),
        }
        result.update(self.custom)
        return result
