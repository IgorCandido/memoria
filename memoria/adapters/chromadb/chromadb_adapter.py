"""
ChromaDB adapter implementing VectorStorePort.

Connects to ChromaDB (HTTP or persistent) and provides vector storage operations.
Must pass all VectorStorePortTests to ensure compatibility.
"""

from typing import Optional

import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings

from memoria.domain.entities import Document, SearchResult
from memoria.domain.ports.vector_store import VectorStorePort


class ChromaDBAdapter:
    """
    Adapter for ChromaDB vector database.

    Implements VectorStorePort protocol for storing and searching document embeddings.
    Supports both HTTP client (for remote ChromaDB) and persistent client (local).
    """

    def __init__(
        self,
        collection_name: str = "memoria_documents",
        db_path: Optional[str] = None,
        use_http: bool = False,
        http_host: str = "localhost",
        http_port: int = 8000,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Initialize ChromaDB adapter.

        Args:
            collection_name: Name of the ChromaDB collection
            db_path: Path for persistent storage (if not using HTTP)
            use_http: Whether to use HTTP client (True) or persistent client (False)
            http_host: Hostname for HTTP client
            http_port: Port for HTTP client
            timeout: HTTP request timeout in seconds (None for default)
        """
        self.collection_name = collection_name
        self.use_http = use_http

        # Build settings with optional timeout
        settings_kwargs: dict = {"anonymized_telemetry": False}
        if timeout is not None:
            settings_kwargs["chroma_server_http_timeout"] = timeout

        # Create appropriate client
        if use_http:
            self._client: ClientAPI = chromadb.HttpClient(
                host=http_host,
                port=http_port,
                settings=Settings(**settings_kwargs),
            )
        else:
            if db_path is None:
                raise ValueError("db_path required when not using HTTP mode")
            self._client = chromadb.PersistentClient(
                path=db_path,
                settings=Settings(anonymized_telemetry=False),
            )

        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Memoria document embeddings"},
        )

    def get_collection(self):
        """Return the underlying ChromaDB collection for direct access."""
        return self._collection

    def add_documents(self, docs: list[Document]) -> None:
        """
        Add documents to the vector store in batches.

        ChromaDB has a max batch size of ~5,461 items. This method handles
        large document sets by batching them into smaller chunks.

        Args:
            docs: List of documents with embeddings to add

        Raises:
            ValueError: If any document is missing an embedding
        """
        if not docs:
            return

        # Validate all docs have embeddings
        for doc in docs:
            if doc.embedding is None:
                raise ValueError(f"Document {doc.id} missing embedding")

        # Batch size - set to 5000 to stay under ChromaDB's limit
        BATCH_SIZE = 5000

        # Process documents in batches
        for i in range(0, len(docs), BATCH_SIZE):
            batch = docs[i:i + BATCH_SIZE]

            # Prepare data for ChromaDB
            ids = [doc.id for doc in batch]
            embeddings = [doc.embedding for doc in batch]
            documents = [doc.content for doc in batch]

            # ChromaDB requires non-empty metadata dicts
            # Add a placeholder if metadata is empty
            metadatas = [
                doc.metadata if doc.metadata else {"_placeholder": "1"}
                for doc in batch
            ]

            # Add batch to collection
            self._collection.add(
                ids=ids,
                embeddings=embeddings,  # type: ignore[arg-type]
                documents=documents,
                metadatas=metadatas,  # type: ignore[arg-type]
            )

    def search(self, query_embedding: list[float], k: int = 5) -> list[SearchResult]:
        """
        Search for similar documents using vector similarity.

        Args:
            query_embedding: Query vector
            k: Number of results to return

        Returns:
            List of search results sorted by relevance (highest first)
        """
        # Query ChromaDB
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
        )

        # Diagnostic logging (can be disabled for production)
        import os
        if os.getenv("MEMORIA_DEBUG"):
            num_results = len(results["ids"][0]) if results["ids"] else 0
            print(f"[DEBUG] ChromaDB returned {num_results} results for k={k}")
            if results.get("distances") and results["distances"][0]:
                distances = results["distances"][0]
                print(f"[DEBUG] Distance range: [{min(distances):.6f}, {max(distances):.6f}]")

        # Convert to SearchResult entities
        search_results: list[SearchResult] = []

        if not results["ids"] or not results["ids"][0]:
            return search_results

        for i in range(len(results["ids"][0])):
            doc_id = results["ids"][0][i]
            content = results["documents"][0][i] if results["documents"] else ""
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0.0

            # Convert distance to similarity score (0-1 range)
            # ChromaDB uses cosine distance: smaller = more similar
            # Similarity = 1 - (distance / 2) since cosine distance is in [0, 2]
            similarity = max(0.0, min(1.0, 1.0 - (distance / 2.0)))

            # Get embedding if available
            embedding = None
            if results.get("embeddings") and results["embeddings"][0]:
                embedding = results["embeddings"][0][i]

            # Create document
            document = Document(
                id=doc_id,
                content=content,
                metadata=metadata,
                embedding=embedding,
            )

            # Create search result
            search_result = SearchResult(
                document=document,
                score=similarity,
                rank=i,
            )
            search_results.append(search_result)

        return search_results

    def get_by_id(self, doc_id: str) -> Document | None:
        """
        Retrieve a document by its ID.

        Args:
            doc_id: Document identifier

        Returns:
            Document if found, None otherwise
        """
        result = self._collection.get(
            ids=[doc_id],
            include=["documents", "metadatas", "embeddings"],
        )

        # Check if document was found
        if not result["ids"] or len(result["ids"]) == 0:
            return None

        # Extract data - ChromaDB returns lists
        content = result["documents"][0] if result.get("documents") is not None else ""
        metadata = result["metadatas"][0] if result.get("metadatas") is not None else {}

        # Handle embeddings carefully (they may be numpy arrays)
        embedding = None
        if result.get("embeddings") is not None and len(result["embeddings"]) > 0:
            embedding = result["embeddings"][0]

        # Remove placeholder metadata if present
        if metadata and metadata.get("_placeholder") == "1" and len(metadata) == 1:
            metadata = {}

        return Document(
            id=doc_id,
            content=content,
            metadata=metadata,
            embedding=embedding,
        )

    def delete(self, doc_id: str) -> bool:
        """
        Delete a document by its ID.

        Args:
            doc_id: Document identifier

        Returns:
            True if document was deleted, False if not found
        """
        try:
            # Check if document exists first
            existing = self.get_by_id(doc_id)
            if existing is None:
                return False

            # Delete from collection
            self._collection.delete(ids=[doc_id])
            return True

        except Exception:
            return False

    def get_stats(self) -> dict[str, int]:
        """
        Get statistics about the vector store.

        Returns:
            Dictionary with count statistics
        """
        count = self._collection.count()
        return {"document_count": count}

    def clear(self) -> None:
        """Clear all documents from the vector store."""
        # Delete the collection and recreate it
        self._client.delete_collection(name=self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Memoria document embeddings"},
        )
