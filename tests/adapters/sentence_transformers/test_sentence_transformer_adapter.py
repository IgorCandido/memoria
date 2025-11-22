"""
Tests for SentenceTransformerAdapter.

Inherits from EmbeddingGeneratorPortTests to ensure full port compliance.
"""

import pytest

from memoria.adapters.sentence_transformers.sentence_transformer_adapter import (
    SentenceTransformerAdapter,
)
from memoria.domain.ports.embedding_generator import EmbeddingGeneratorPort
from tests.ports.test_embedding_generator_port import EmbeddingGeneratorPortTests


class TestSentenceTransformerAdapter(EmbeddingGeneratorPortTests):
    """
    Test SentenceTransformerAdapter against EmbeddingGeneratorPort contract.

    Inherits all port tests from EmbeddingGeneratorPortTests.
    Only needs to implement the create_generator() factory method.
    """

    def create_generator(self) -> EmbeddingGeneratorPort:
        """
        Factory method to create a SentenceTransformerAdapter instance.

        Required by EmbeddingGeneratorPortTests base class.
        """
        # Use a small, fast model for testing
        return SentenceTransformerAdapter(
            model_name="all-MiniLM-L6-v2",
            show_progress=False,
        )

    def test_lazy_loading(self) -> None:
        """Test that model is lazy-loaded on first use."""
        adapter = SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")

        # Model should not be loaded yet
        assert adapter._model is None

        # Access dimensions property - should trigger model load
        dims = adapter.dimensions

        # Model should now be loaded
        assert adapter._model is not None
        assert dims > 0

    def test_model_name_property(self) -> None:
        """Test that model_name property returns the model name."""
        adapter = SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")
        assert adapter.model_name == "all-MiniLM-L6-v2"
