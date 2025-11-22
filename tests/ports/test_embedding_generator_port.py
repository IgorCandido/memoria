"""
Port test base class for EmbeddingGeneratorPort.

All EmbeddingGenerator adapters (SentenceTransformers, OpenAI, etc.)
must pass these tests.
"""

from abc import ABC, abstractmethod

import pytest

from memoria.domain.ports.embedding_generator import EmbeddingGeneratorPort
from memoria.domain.value_objects import Embedding


class EmbeddingGeneratorPortTests(ABC):
    """
    Base test suite for all EmbeddingGenerator adapters.

    To test a new adapter:
    1. Inherit from this class
    2. Implement create_generator() to return your adapter
    3. Run pytest - all tests execute automatically
    """

    @abstractmethod
    def create_generator(self) -> EmbeddingGeneratorPort:
        """
        Factory method - subclasses must implement.

        Returns:
            A configured instance of the adapter under test
        """
        ...

    @pytest.fixture
    def generator(self) -> EmbeddingGeneratorPort:
        """Fixture that provides a generator for each test."""
        return self.create_generator()

    def test_embed_text_returns_embedding(self, generator: EmbeddingGeneratorPort) -> None:
        """Test that embed_text returns a valid Embedding."""
        embedding = generator.embed_text("test text")
        assert isinstance(embedding, Embedding)
        assert embedding.dimensions > 0

    def test_embed_text_consistent_dimensions(
        self, generator: EmbeddingGeneratorPort
    ) -> None:
        """Test that all embeddings have the same dimensions."""
        emb1 = generator.embed_text("first text")
        emb2 = generator.embed_text("second text")
        assert emb1.dimensions == emb2.dimensions
        assert emb1.dimensions == generator.dimensions

    def test_embed_text_different_inputs_different_embeddings(
        self, generator: EmbeddingGeneratorPort
    ) -> None:
        """Test that different texts produce different embeddings."""
        emb1 = generator.embed_text("python programming")
        emb2 = generator.embed_text("cooking recipes")
        assert emb1.vector != emb2.vector

    def test_embed_batch_returns_list(self, generator: EmbeddingGeneratorPort) -> None:
        """Test that embed_batch returns a list of embeddings."""
        texts = ["first", "second", "third"]
        embeddings = generator.embed_batch(texts)
        assert len(embeddings) == 3
        assert all(isinstance(emb, Embedding) for emb in embeddings)

    def test_embed_batch_preserves_order(self, generator: EmbeddingGeneratorPort) -> None:
        """Test that embed_batch preserves input order."""
        texts = ["alpha", "beta", "gamma"]
        embeddings = generator.embed_batch(texts)

        # Each batch embedding should match individual embedding
        for text, batch_emb in zip(texts, embeddings):
            individual_emb = generator.embed_text(text)
            # Embeddings should be identical (or very close due to floating point)
            assert batch_emb.dimensions == individual_emb.dimensions

    def test_embed_batch_consistent_dimensions(
        self, generator: EmbeddingGeneratorPort
    ) -> None:
        """Test that all batch embeddings have consistent dimensions."""
        texts = ["first", "second", "third"]
        embeddings = generator.embed_batch(texts)
        dimensions = embeddings[0].dimensions
        assert all(emb.dimensions == dimensions for emb in embeddings)

    def test_dimensions_property(self, generator: EmbeddingGeneratorPort) -> None:
        """Test that dimensions property returns a positive integer."""
        dims = generator.dimensions
        assert isinstance(dims, int)
        assert dims > 0

    def test_model_name_property(self, generator: EmbeddingGeneratorPort) -> None:
        """Test that model_name property returns a non-empty string."""
        name = generator.model_name
        assert isinstance(name, str)
        assert len(name) > 0
