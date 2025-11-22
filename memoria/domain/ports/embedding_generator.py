"""
EmbeddingGeneratorPort - Protocol for generating text embeddings.

This port defines the contract for converting text to vector embeddings.
Any embedding model (SentenceTransformers, OpenAI, Cohere, etc.) can
implement this port.
"""

from typing import Protocol

from ..value_objects import Embedding


class EmbeddingGeneratorPort(Protocol):
    """
    Port for generating embeddings from text.

    Embeddings are vector representations of text that capture semantic meaning.
    """

    def embed_text(self, text: str) -> Embedding:
        """
        Generate an embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector

        Raises:
            ValueError: If text is empty
            RuntimeError: If model fails to generate embedding
        """
        ...

    def embed_batch(self, texts: list[str]) -> list[Embedding]:
        """
        Generate embeddings for multiple texts efficiently.

        This is typically faster than calling embed_text() multiple times
        as the model can batch process inputs.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings in same order as input texts

        Raises:
            ValueError: If texts list is empty or contains empty strings
            RuntimeError: If model fails to generate embeddings
        """
        ...

    @property
    def dimensions(self) -> int:
        """
        Get the dimensionality of embeddings produced by this generator.

        Returns:
            Number of dimensions (e.g., 384, 768, 1536)
        """
        ...

    @property
    def model_name(self) -> str:
        """
        Get the name of the embedding model being used.

        Returns:
            Model name (e.g., "all-MiniLM-L6-v2")
        """
        ...
