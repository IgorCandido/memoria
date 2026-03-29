"""
Unit tests for EmbeddingGeneratorPort contract using EmbeddingGeneratorStub.

All tests run in-memory — no external services required.
Structural conformance checks verify adapter signatures match the port.
"""

import pytest

from memoria.adapters.stubs.embedding_generator_stub import EmbeddingGeneratorStub


@pytest.fixture()
def stub() -> EmbeddingGeneratorStub:
    return EmbeddingGeneratorStub(dimensions=1024)


class TestEmbedText:
    def test_returns_embedding_of_correct_dimension(self, stub):
        emb = stub.embed_text("Hello world")
        assert len(emb.vector) == 1024

    def test_deterministic_output(self, stub):
        emb1 = stub.embed_text("Hello world")
        emb2 = stub.embed_text("Hello world")
        assert emb1.vector == emb2.vector

    def test_different_inputs_differ(self, stub):
        emb1 = stub.embed_text("Hello world")
        emb2 = stub.embed_text("Goodbye world")
        assert emb1.vector != emb2.vector

    def test_raises_on_empty_text(self, stub):
        with pytest.raises(ValueError):
            stub.embed_text("")

    def test_to_list_returns_floats(self, stub):
        emb = stub.embed_text("test")
        values = emb.to_list()
        assert all(isinstance(v, float) for v in values)


class TestEmbedBatch:
    def test_returns_correct_count(self, stub):
        texts = ["first", "second", "third"]
        embeddings = stub.embed_batch(texts)
        assert len(embeddings) == 3

    def test_each_embedding_has_correct_dimension(self, stub):
        embeddings = stub.embed_batch(["a", "b"])
        for emb in embeddings:
            assert len(emb.vector) == 1024

    def test_raises_on_empty_list(self, stub):
        with pytest.raises(ValueError):
            stub.embed_batch([])

    def test_raises_on_empty_string_in_list(self, stub):
        with pytest.raises(ValueError):
            stub.embed_batch(["valid", ""])


class TestDimensions:
    def test_default_dimensions(self, stub):
        assert stub.dimensions == 1024

    def test_custom_dimensions(self):
        small = EmbeddingGeneratorStub(dimensions=384)
        emb = small.embed_text("test")
        assert len(emb.vector) == 384
        assert small.dimensions == 384


class TestModelName:
    def test_default_model_name(self, stub):
        assert stub.model_name == "stub-model"

    def test_custom_model_name(self):
        custom = EmbeddingGeneratorStub(model_name="my-model")
        assert custom.model_name == "my-model"


class TestStructuralConformance:
    """Verify adapter classes have the required port methods (duck-type check)."""

    def test_ollama_adapter_has_port_methods(self):
        from memoria.adapters.ollama.ollama_embedding_adapter import OllamaEmbeddingAdapter
        assert hasattr(OllamaEmbeddingAdapter, "embed_text")
        assert hasattr(OllamaEmbeddingAdapter, "embed_batch")
        # Check as properties on the class (descriptor) or instance
        adapter = OllamaEmbeddingAdapter.__new__(OllamaEmbeddingAdapter)
        assert hasattr(type(adapter), "dimensions") or hasattr(adapter, "dimensions")
        assert hasattr(type(adapter), "model_name") or hasattr(adapter, "model_name")

    def test_stub_has_port_methods(self, stub):
        assert callable(getattr(stub, "embed_text", None))
        assert callable(getattr(stub, "embed_batch", None))
        assert isinstance(stub.dimensions, int)
        assert isinstance(stub.model_name, str)
