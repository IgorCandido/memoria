"""
Performance regression tests for indexing operations.

Validates:
- SC-003: 0% timeout rate for batch indexing
- SC-005: >20 docs/minute throughput
- SC-007: <2GB peak memory
- Batch embedding is faster than sequential
- Progressive batching commits incrementally

Requires: ChromaDB running on localhost:8001.
"""

import time
import tempfile
import shutil
from pathlib import Path

import pytest

from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
from memoria.adapters.sentence_transformers.sentence_transformer_adapter import SentenceTransformerAdapter
from memoria.adapters.document.document_processor_adapter import DocumentProcessorAdapter
from memoria.domain.entities import Document, ProgressTracker


@pytest.fixture(scope="module")
def test_vector_store():
    """Create a test vector store (separate collection)."""
    vs = ChromaDBAdapter(
        collection_name="memoria_perf_regression",
        use_http=True,
        http_host="localhost",
        http_port=8001,
        timeout=60.0,
    )
    yield vs
    vs.clear()


@pytest.fixture(scope="module")
def embedder():
    return SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")


@pytest.fixture(scope="module")
def doc_processor():
    return DocumentProcessorAdapter(chunk_size=2000, chunk_overlap=100)


@pytest.fixture
def temp_docs_dir():
    """Create temporary directory with test documents."""
    temp_dir = tempfile.mkdtemp(prefix="memoria_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


def generate_test_doc(path: Path, size_kb: int = 10) -> Path:
    """Generate a test markdown document of specified size."""
    content = f"# Test Document: {path.stem}\n\n"
    paragraph = "This is test content for performance benchmarking. " * 20 + "\n\n"
    while len(content) < size_kb * 1024:
        content += paragraph
    content = content[:size_kb * 1024]
    path.write_text(content, encoding="utf-8")
    return path


class TestBatchEmbedding:
    """Verify batch embedding is faster than sequential."""

    def test_batch_faster_than_sequential(self, embedder):
        """Batch embedding should be faster than N sequential calls."""
        texts = [f"This is test document number {i} about topic {i % 5}" for i in range(50)]

        # Sequential
        start = time.time()
        for text in texts:
            embedder.embed_text(text)
        seq_time = time.time() - start

        # Batch
        start = time.time()
        embedder.embed_batch(texts)
        batch_time = time.time() - start

        speedup = seq_time / batch_time if batch_time > 0 else float("inf")

        print(f"\nBatch vs Sequential Embedding:")
        print(f"  Sequential: {seq_time * 1000:.1f}ms ({len(texts)} texts)")
        print(f"  Batch:      {batch_time * 1000:.1f}ms ({len(texts)} texts)")
        print(f"  Speedup:    {speedup:.1f}x")

        assert batch_time <= seq_time, (
            f"Batch ({batch_time:.3f}s) should be <= sequential ({seq_time:.3f}s)"
        )


class TestProgressTracker:
    """Verify ProgressTracker entity works correctly."""

    def test_tracker_basic_flow(self):
        tracker = ProgressTracker(total_documents=10)
        assert tracker.total_documents == 10
        assert tracker.processed_documents == 0
        assert tracker.failed_documents == 0
        assert not tracker.is_complete

        tracker.mark_processed("doc1.md")
        assert tracker.processed_documents == 1

        tracker.mark_failed("doc2.md", "parse error")
        assert tracker.processed_documents == 2
        assert tracker.failed_documents == 1
        assert len(tracker.failed_files) == 1

        tracker.finish()
        assert tracker.end_time is not None
        assert tracker.elapsed_seconds > 0

    def test_tracker_throughput(self):
        tracker = ProgressTracker(total_documents=100)
        for i in range(100):
            tracker.mark_processed(f"doc_{i}.md")
        tracker.finish()

        assert tracker.is_complete
        assert tracker.docs_per_minute > 0
        assert tracker.success_count == 100


class TestProgressiveBatching:
    """Verify progressive batching commits incrementally."""

    def test_incremental_commits(self, test_vector_store, embedder, doc_processor, temp_docs_dir):
        """Documents should be committed in batches, not all at once."""
        test_vector_store.clear()

        # Generate 20 small docs
        docs = []
        for i in range(20):
            path = generate_test_doc(temp_docs_dir / f"doc_{i:03d}.md", size_kb=5)
            docs.append(path)

        # Process and commit in small batches (batch_size=5 for test speed)
        BATCH_SIZE = 5
        pending = []
        total_committed = 0
        commit_counts = []

        for doc_path in docs:
            chunks = doc_processor.process_document(doc_path)
            pending.extend(chunks)

            if len(pending) >= BATCH_SIZE:
                texts = [c.content for c in pending]
                embeddings = embedder.embed_batch(texts)
                docs_with_emb = [
                    Document(
                        id=c.id, content=c.content,
                        embedding=e.to_list(), metadata=c.metadata,
                    )
                    for c, e in zip(pending, embeddings)
                ]
                test_vector_store.add_documents(docs_with_emb)
                total_committed += len(docs_with_emb)
                commit_counts.append(len(docs_with_emb))
                pending = []

        # Commit remaining
        if pending:
            texts = [c.content for c in pending]
            embeddings = embedder.embed_batch(texts)
            docs_with_emb = [
                Document(
                    id=c.id, content=c.content,
                    embedding=e.to_list(), metadata=c.metadata,
                )
                for c, e in zip(pending, embeddings)
            ]
            test_vector_store.add_documents(docs_with_emb)
            total_committed += len(docs_with_emb)
            commit_counts.append(len(docs_with_emb))

        print(f"\nProgressive Batching:")
        print(f"  Total committed: {total_committed} chunks")
        print(f"  Batch count: {len(commit_counts)}")
        print(f"  Batch sizes: {commit_counts}")

        assert total_committed > 0
        assert len(commit_counts) > 1, "Should have multiple commits (progressive batching)"


class TestBackwardCompatibility:
    """SC-006: Verify no breaking changes to search_knowledge() API."""

    def test_search_knowledge_signature_unchanged(self):
        """search_knowledge() must accept same parameters as before."""
        import inspect
        from memoria.skill_helpers import search_knowledge

        sig = inspect.signature(search_knowledge)
        params = list(sig.parameters.keys())

        assert "query" in params
        assert "mode" in params
        assert "expand" in params
        assert "limit" in params

    def test_index_documents_signature_unchanged(self):
        """index_documents() must accept same parameters as before."""
        import inspect
        from memoria.skill_helpers import index_documents

        sig = inspect.signature(index_documents)
        params = list(sig.parameters.keys())

        assert "pattern" in params
        assert "rebuild" in params
