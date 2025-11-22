"""Test that EmbeddingGeneratorStub passes all EmbeddingGeneratorPortTests."""

from memoria.adapters.stubs.embedding_generator_stub import EmbeddingGeneratorStub
from memoria.domain.ports.embedding_generator import EmbeddingGeneratorPort
from tests.ports.test_embedding_generator_port import EmbeddingGeneratorPortTests


class TestEmbeddingGeneratorStub(EmbeddingGeneratorPortTests):
    """
    Test EmbeddingGeneratorStub implementation.

    By inheriting from EmbeddingGeneratorPortTests, this stub automatically
    runs all 8 port tests to ensure it behaves correctly.
    """

    def create_generator(self) -> EmbeddingGeneratorPort:
        """Create an EmbeddingGeneratorStub instance for testing."""
        return EmbeddingGeneratorStub(dimensions=384, model_name="test-stub")
