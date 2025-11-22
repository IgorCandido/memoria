"""
Stub implementation of EmbeddingGeneratorPort.

Returns deterministic embeddings for testing purposes.
"""

import hashlib

from memoria.domain.value_objects import Embedding


class EmbeddingGeneratorStub:
    """
    Stub embedding generator that creates deterministic embeddings.

    Uses hash of text to create consistent but distinct embeddings
    for different inputs. Not semantically meaningful, but sufficient
    for testing.
    """

    def __init__(self, dimensions: int = 384, model_name: str = "stub-model") -> None:
        """
        Initialize stub generator.

        Args:
            dimensions: Number of dimensions for embeddings
            model_name: Name to report for this model
        """
        self._dimensions = dimensions
        self._model_name = model_name

    def embed_text(self, text: str) -> Embedding:
        """Generate a deterministic embedding from text."""
        if not text:
            raise ValueError("Text cannot be empty")

        # Use hash to create deterministic vector
        vector = self._text_to_vector(text)
        return Embedding(vector=vector)

    def embed_batch(self, texts: list[str]) -> list[Embedding]:
        """Generate embeddings for multiple texts."""
        if not texts:
            raise ValueError("Texts list cannot be empty")
        if any(not t for t in texts):
            raise ValueError("Texts list cannot contain empty strings")

        return [self.embed_text(text) for text in texts]

    @property
    def dimensions(self) -> int:
        """Return embedding dimensionality."""
        return self._dimensions

    @property
    def model_name(self) -> str:
        """Return model name."""
        return self._model_name

    def _text_to_vector(self, text: str) -> list[float]:
        """
        Convert text to a deterministic vector using hashing.

        This creates a normalized vector where each dimension is derived
        from the hash of (text + dimension_index).
        """
        vector: list[float] = []
        for i in range(self._dimensions):
            # Hash text with dimension index
            hash_input = f"{text}_{i}".encode("utf-8")
            hash_bytes = hashlib.sha256(hash_input).digest()

            # Convert first 8 bytes to float in [-1, 1]
            hash_int = int.from_bytes(hash_bytes[:8], byteorder="big")
            # Normalize to [-1, 1]
            normalized = (hash_int / (2**64)) * 2 - 1
            vector.append(normalized)

        # Normalize vector to unit length (for cosine similarity)
        magnitude = sum(x * x for x in vector) ** 0.5
        if magnitude > 0:
            vector = [x / magnitude for x in vector]

        return vector
