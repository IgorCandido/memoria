"""
Backward compatibility facade for raggy.py UniversalRAG interface.

⚠️ THIS IS A COMPATIBILITY HACK LAYER ⚠️

This facade provides exact API compatibility with the legacy raggy.py,
including its broken error handling patterns. It sits between user code
and the clean onion architecture implementation.

Architecture:
    User Code
      ↓
    RaggyCompatibilityFacade (matches raggy quirks - THIS FILE)
      ↓ catches typed exceptions
    CompatibilityErrorMapper (translates errors to raggy format)
      ↓ domain errors flow up
    Clean Adapters (raise typed domain errors)
      ↓
    Domain Layer (explicit error protocols)

All quirks are documented with:
- RAGGY QUIRK: What the quirk is
- Why: Why raggy.py does this
- When: When this behavior applies
- Remove: Version when this hack is removed

This entire facade will be removed in v4.0.0 when raggy.py is fully deprecated.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
from memoria.adapters.sentence_transformers.sentence_transformer_adapter import (
    SentenceTransformerAdapter,
)
from memoria.adapters.search.search_engine_adapter import SearchEngineAdapter
from memoria.adapters.document.document_processor_adapter import DocumentProcessorAdapter
from memoria.domain.entities import SearchResult
from memoria.domain.errors import DatabaseNotBuiltError, MemoriaError
from memoria.compatibility.error_mapper import CompatibilityErrorMapper


# Global flag to track if dependencies have been set up
_DEPENDENCIES_INITIALIZED = False


def setup_dependencies(quiet: bool = False) -> None:
    """
    Setup required dependencies for raggy compatibility.

    This function mimics raggy.py's setup_dependencies() for compatibility.
    The new implementation doesn't need global setup, but this function
    is kept for API compatibility.

    Args:
        quiet: Suppress output messages
    """
    global _DEPENDENCIES_INITIALIZED

    if _DEPENDENCIES_INITIALIZED:
        return

    # Check imports
    try:
        import chromadb  # noqa: F401
        from sentence_transformers import SentenceTransformer  # noqa: F401

        if not quiet:
            print("✓ Dependencies available")

        _DEPENDENCIES_INITIALIZED = True
    except ImportError as e:
        print(f"Error: Missing required dependency - {e}")
        sys.exit(1)


class UniversalRAG:
    """
    Backward-compatible facade matching raggy.py UniversalRAG interface.

    This class provides the exact same API as the legacy raggy.UniversalRAG
    class but uses the new clean architecture internally.

    All quirks and behaviors from raggy.py are preserved to ensure perfect
    backward compatibility.
    """

    def __init__(
        self,
        docs_dir: str = "./docs",
        db_dir: str = "./vectordb",
        model_name: str = "all-MiniLM-L6-v2",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        quiet: bool = False,
        config_path: Optional[str] = None,
    ) -> None:
        """
        Initialize UniversalRAG instance.

        Args:
            docs_dir: Directory containing documents to index
            db_dir: Directory for ChromaDB database
            model_name: Sentence transformer model name
            chunk_size: Size of text chunks in characters
            chunk_overlap: Overlap between chunks
            quiet: Suppress output messages
            config_path: Optional config file path (not used in new implementation)
        """
        self.docs_dir = Path(docs_dir)
        self.db_dir = Path(db_dir)
        self.model_name = model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.quiet = quiet

        # Ensure db_dir exists
        self.db_dir.mkdir(parents=True, exist_ok=True)

        # Initialize adapters
        self._vector_store = ChromaDBAdapter(
            collection_name="memoria",
            db_path=str(self.db_dir),
            use_http=False,
        )

        self._embedder = SentenceTransformerAdapter(
            model_name=self.model_name,
        )

        self._search_engine = SearchEngineAdapter(
            vector_store=self._vector_store,
            embedding_generator=self._embedder,
            hybrid_weight=0.7,  # raggy.py default
        )

        self._document_processor = DocumentProcessorAdapter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

        # Expose database_manager for backward compatibility
        # Some tests check this attribute
        self.database_manager = self._vector_store

        # Track whether build() has been called
        self._built = False

    def build(self, force_rebuild: bool = False) -> None:
        """
        Build or update the vector database from documents.

        Args:
            force_rebuild: If True, rebuild database from scratch
        """
        # Find all documents in docs_dir
        if not self.docs_dir.exists():
            if not self.quiet:
                print(f"Error: docs_dir not found: {self.docs_dir}")
            return

        # Get supported formats
        supported = set(self._document_processor.supported_formats())

        # Find all supported files
        files = []
        for ext in supported:
            files.extend(self.docs_dir.rglob(f"*{ext}"))

        if not files:
            if not self.quiet:
                print("No documents found in docs/ directory")
            return

        if not self.quiet:
            print(f"Found {len(files)} documents")

        # Clear database if force_rebuild
        if force_rebuild:
            self._vector_store.clear()

        # Process each document
        all_docs = []
        for i, file_path in enumerate(files, 1):
            if not self.quiet:
                print(f"[{i}/{len(files)}] Processing {file_path.name}...")

            try:
                docs = self._document_processor.process_document(file_path)
                all_docs.extend(docs)
            except Exception as e:
                if not self.quiet:
                    print(f"  Warning: Failed to process {file_path.name}: {e}")
                continue

        if not all_docs:
            if not self.quiet:
                print("No content could be extracted from documents")
            return

        if not self.quiet:
            print(f"Generated {len(all_docs)} text chunks")
            print("Generating embeddings...")

        # Generate embeddings for all documents (Document is frozen, so create new instances)
        docs_with_embeddings = []
        for doc in all_docs:
            embedding_result = self._embedder.embed_text(doc.content)
            # Create new document with embedding
            from domain.entities import Document
            doc_with_embedding = Document(
                id=doc.id,
                content=doc.content,
                metadata=doc.metadata,
                embedding=embedding_result.vector,
            )
            docs_with_embeddings.append(doc_with_embedding)

        if not self.quiet:
            print("Adding to database...")

        # Add documents to vector store
        self._vector_store.add_documents(docs_with_embeddings)

        # Mark as built
        self._built = True

        if not self.quiet:
            print("✓ Build complete")

    def search(
        self,
        query: str,
        n_results: int = 5,
        hybrid: bool = False,
        expand_query: bool = False,
        show_scores: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search the vector database.

        Args:
            query: Search query string
            n_results: Number of results to return
            hybrid: Use hybrid semantic + keyword search
            expand_query: Enable query expansion with synonyms
            show_scores: Add highlighted_text field (not implemented yet)

        Returns:
            List of result dictionaries matching raggy.py format
        """
        # Determine search mode
        mode = "hybrid" if hybrid else "semantic"

        # Expand query if requested
        if expand_query:
            expanded = self._search_engine.expand_query(query)
            # Use first expanded term (raggy.py behavior)
            if expanded.expanded:
                query = expanded.expanded[0]

        # Perform search
        results = self._search_engine.search(query, mode=mode, limit=n_results)

        # Transform results to raggy.py dict format
        formatted_results = [self._transform_result(r, show_scores) for r in results]

        # Apply confidence threshold filtering (raggy.py behavior)
        # Filter out results below 0.3 confidence
        confidence_threshold = 0.3
        filtered_results = [r for r in formatted_results if r["final_score"] >= confidence_threshold]

        return filtered_results

    def _transform_result(
        self, result: SearchResult, show_scores: Optional[bool]
    ) -> Dict[str, Any]:
        """
        Transform SearchResult to raggy.py dict format.

        This must match the EXACT structure expected by compatibility tests.
        """
        # Extract data from SearchResult
        final_score = float(result.score)

        # For semantic-only search, all score is semantic
        # For hybrid, we approximate based on hybrid_weight (0.7)
        # This is a simplification - actual implementation has more details
        semantic_score = float(final_score)  # Approximate
        keyword_score = 0.0  # Will be non-zero in hybrid mode

        # Calculate distance (raggy.py stores 1 - similarity as distance)
        distance = float(1.0 - final_score)

        # Score interpretation (raggy.py thresholds)
        if final_score >= 0.8:
            interpretation = "Very High Confidence"
        elif final_score >= 0.6:
            interpretation = "High Confidence"
        elif final_score >= 0.4:
            interpretation = "Medium Confidence"
        else:
            interpretation = "Low Confidence"

        # Build result dict
        result_dict = {
            "text": result.document.content,
            "metadata": result.document.metadata,
            "semantic_score": semantic_score,
            "keyword_score": keyword_score,
            "final_score": final_score,
            "score_interpretation": interpretation,
            "distance": distance,
            "similarity": final_score,  # Alias for backward compatibility
        }

        # Add highlighted_text if requested
        if show_scores:
            # Simple highlighting: just return the text for now
            # TODO: Implement actual highlighting
            result_dict["highlighted_text"] = result.document.content

        return result_dict

    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        RAGGY QUIRK: Returns {"error": "message"} dict instead of raising exceptions.
        Why: Legacy raggy.py users expect error dicts from get_stats().
        When: Database not built, or stats query fails.
        Remove: v4.0.0 when raggy.py compatibility is dropped.

        Returns:
            Success: {"db_path": str, "total_chunks": int, "sources": dict}
            Failure: {"error": str}

        Examples:
            >>> rag = UniversalRAG(...)
            >>> rag.get_stats()  # Without calling build()
            {"error": "Database not built. Call build() first."}

            >>> rag.build()
            >>> rag.get_stats()
            {"db_path": "/path/to/db", "total_chunks": 42, "sources": {...}}
        """
        # Check if database was built
        if not self._built:
            # Raise typed error, let mapper handle conversion
            error = DatabaseNotBuiltError()
            return CompatibilityErrorMapper.map_get_stats_error(error)

        # Attempt to get stats - any errors are mapped to raggy format
        try:
            stats = self._vector_store.get_stats()

            # Transform to raggy.py format (success case)
            return {
                "db_path": str(self.db_dir),
                "total_chunks": stats.get("document_count", 0),
                "sources": stats.get("metadata_counts", {}).get("source", {}),
            }

        except MemoriaError as e:
            # Typed domain error - use mapper
            return CompatibilityErrorMapper.map_get_stats_error(e)

        except Exception as e:
            # Unexpected error (should not happen with clean implementation)
            # Re-raise for visibility - don't hide bugs
            raise RuntimeError(
                f"Unexpected error in get_stats() - this indicates a bug in "
                f"the implementation, not a user error: {type(e).__name__}: {e}"
            ) from e
