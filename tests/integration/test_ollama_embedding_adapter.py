"""
Integration tests for OllamaEmbeddingAdapter.

Requires live Ollama on relishhost2:11434 with mxbai-embed-large pulled.
Run with: pytest --run-integration tests/integration/test_ollama_embedding_adapter.py
"""

import pytest

from memoria.adapters.ollama.ollama_embedding_adapter import OllamaEmbeddingAdapter


@pytest.fixture()
def adapter() -> OllamaEmbeddingAdapter:
    return OllamaEmbeddingAdapter()


@pytest.mark.integration
class TestEmbedText:
    def test_returns_1024_dimension_vector(self, adapter):
        emb = adapter.embed_text("Hello world")
        assert len(emb.vector) == 1024

    def test_all_floats(self, adapter):
        emb = adapter.embed_text("Test text")
        assert all(isinstance(v, float) for v in emb.vector)

    def test_raises_on_empty_text(self, adapter):
        with pytest.raises(ValueError):
            adapter.embed_text("")

    def test_different_texts_produce_different_embeddings(self, adapter):
        emb1 = adapter.embed_text("Hello world")
        emb2 = adapter.embed_text("Goodbye world")
        assert emb1.vector != emb2.vector

    def test_same_text_produces_same_embedding(self, adapter):
        emb1 = adapter.embed_text("Hello world")
        emb2 = adapter.embed_text("Hello world")
        assert emb1.vector == emb2.vector


@pytest.mark.integration
class TestEmbedBatch:
    def test_returns_correct_count(self, adapter):
        texts = ["first sentence", "second sentence", "third sentence"]
        embeddings = adapter.embed_batch(texts)
        assert len(embeddings) == 3

    def test_each_embedding_has_correct_dimension(self, adapter):
        embeddings = adapter.embed_batch(["text one", "text two"])
        for emb in embeddings:
            assert len(emb.vector) == 1024

    def test_raises_on_empty_list(self, adapter):
        with pytest.raises(ValueError):
            adapter.embed_batch([])


@pytest.mark.integration
class TestProperties:
    def test_dimensions_returns_1024(self, adapter):
        assert adapter.dimensions == 1024

    def test_model_name_is_mxbai(self, adapter):
        assert "mxbai" in adapter.model_name
