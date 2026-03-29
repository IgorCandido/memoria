"""
OllamaEmbeddingAdapter - Ollama implementation of EmbeddingGeneratorPort.

Calls the Ollama embedding API on relishhost2 using the official ollama Python library.
Default model: mxbai-embed-large (1024-dimension vectors).
Connection parameters read from MEMORIA_OLLAMA_* environment variables.
"""

import os

import ollama

from memoria.domain.value_objects import Embedding


class OllamaEmbeddingAdapter:
    """
    Embedding generator backed by Ollama on relishhost2.

    Uses mxbai-embed-large (1024 dims) by default.
    Active when MEMORIA_EMBEDDING_ADAPTER=ollama (the default).
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        model_name: str | None = None,
    ) -> None:
        resolved_host = host or os.getenv("MEMORIA_OLLAMA_HOST")
        resolved_port_str = port or os.getenv("MEMORIA_OLLAMA_PORT")
        if not resolved_host or not resolved_port_str:
            raise RuntimeError(
                "MEMORIA_OLLAMA_HOST and MEMORIA_OLLAMA_PORT must be set. "
                "Run: bash install-plugin.sh (from memoria plugin dir) to configure ~/.claude/memoria.env"
            )
        resolved_port = int(resolved_port_str)
        self._model_name = model_name or os.getenv("MEMORIA_OLLAMA_MODEL", "mxbai-embed-large")
        self._client = ollama.Client(host=f"http://{resolved_host}:{resolved_port}")

    def embed_text(self, text: str) -> Embedding:
        """
        Generate an embedding for a single text.

        Args:
            text: Text to embed (must be non-empty)

        Returns:
            Embedding wrapping the 1024-float vector from Ollama

        Raises:
            ValueError: If text is empty
            RuntimeError: If Ollama API call fails
        """
        if not text or not text.strip():
            raise ValueError("text cannot be empty")
        try:
            response = self._client.embeddings(model=self._model_name, prompt=text)
            return Embedding(vector=list(response["embedding"]))
        except Exception as exc:
            raise RuntimeError(f"Ollama embedding failed for model {self._model_name}: {exc}") from exc

    def embed_batch(self, texts: list[str]) -> list[Embedding]:
        """
        Generate embeddings for multiple texts.

        Calls embed_text sequentially (Ollama handles its own batching internally).

        Args:
            texts: Non-empty list of non-empty strings

        Returns:
            List of Embedding objects in same order as input
        """
        if not texts:
            raise ValueError("texts list cannot be empty")
        return [self.embed_text(text) for text in texts]

    @property
    def dimensions(self) -> int:
        """Return embedding dimension (1024 for mxbai-embed-large)."""
        # Determined by the model — mxbai-embed-large produces 1024-dim vectors
        return 1024

    @property
    def model_name(self) -> str:
        """Return the Ollama model name being used."""
        return self._model_name
