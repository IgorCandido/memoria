"""
SentenceTransformer adapter implementing EmbeddingGeneratorPort.

Uses sentence-transformers library to generate text embeddings.
Must pass all EmbeddingGeneratorPortTests to ensure compatibility.
"""

from typing import Optional

from sentence_transformers import SentenceTransformer

from memoria.domain.ports.embedding_generator import EmbeddingGeneratorPort
from memoria.domain.value_objects import Embedding


class SentenceTransformerAdapter:
    """
    Adapter for SentenceTransformer embedding generation.

    Implements EmbeddingGeneratorPort protocol using sentence-transformers library.
    Supports batch processing and lazy model loading.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None,
        show_progress: bool = False,
    ) -> None:
        """
        Initialize SentenceTransformer adapter.

        Args:
            model_name: Name or path of the model to use
            device: Device to run model on ("cpu", "cuda", or None for auto)
            show_progress: Whether to show progress bars during encoding
        """
        self._model_name = model_name
        self._device = device
        self._show_progress = show_progress
        self._model: Optional[SentenceTransformer] = None
        self._dimensions_cache: Optional[int] = None

    @property
    def model(self) -> SentenceTransformer:
        """
        Lazy-load the SentenceTransformer model.

        Returns:
            Loaded SentenceTransformer instance
        """
        if self._model is None:
            self._model = SentenceTransformer(
                self._model_name,
                device=self._device,
            )
        return self._model

    @property
    def dimensions(self) -> int:
        """
        Get the embedding dimensions for this model.

        Returns:
            Number of dimensions in embeddings
        """
        if self._dimensions_cache is None:
            # Get dimensions by encoding a test string
            test_embedding = self.model.encode("test", convert_to_numpy=True)
            self._dimensions_cache = len(test_embedding)
        return self._dimensions_cache

    @property
    def model_name(self) -> str:
        """
        Get the model name.

        Returns:
            Model identifier
        """
        return self._model_name

    def embed_text(self, text: str) -> Embedding:
        """
        Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            Embedding value object with vector
        """
        # Encode the text
        vector = self.model.encode(
            text,
            convert_to_numpy=True,
            show_progress_bar=False,  # No progress for single text
        )

        # Convert numpy array to list
        vector_list = vector.tolist()

        return Embedding(vector=vector_list)

    def embed_batch(self, texts: list[str]) -> list[Embedding]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of input texts to embed

        Returns:
            List of Embedding value objects
        """
        if not texts:
            return []

        # Batch encode all texts
        vectors = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=self._show_progress,
            batch_size=32,  # Efficient batch size
        )

        # Convert to Embedding objects
        embeddings = [
            Embedding(vector=vector.tolist())
            for vector in vectors
        ]

        return embeddings
