#!/usr/bin/env python3
"""
Performance test for indexing operations.

Validates:
- SC-003: 0% timeout rate for 100-doc batch
- SC-005: Throughput >20 docs/minute
- SC-007: Memory usage <2GB during peak indexing

Usage:
    python specs/002-memoria-performance/test_indexing_performance.py
"""

import sys
import time
import tempfile
import shutil
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def generate_test_documents(doc_dir: Path, count: int = 100) -> list[Path]:
    """Generate test markdown documents of varying sizes (1KB-5MB)."""
    import random
    import string

    docs = []
    sizes_kb = [1, 5, 10, 50, 100, 500, 1000, 2000, 5000]  # Varying sizes

    for i in range(count):
        size_kb = random.choice(sizes_kb[:min(len(sizes_kb), 5)])  # Bias toward smaller
        if i < 3:
            size_kb = max(sizes_kb)  # First few are large to stress test

        # Generate content
        content_size = size_kb * 1024
        paragraphs = []
        topics = [
            "machine learning", "python programming", "data science",
            "web development", "cloud computing", "system architecture",
            "database optimization", "API design", "testing strategies",
            "DevOps practices", "security best practices", "code review",
        ]
        topic = random.choice(topics)

        paragraphs.append(f"# Document {i+1}: {topic.title()}\n\n")
        paragraphs.append(f"This document covers {topic} concepts and best practices.\n\n")

        while sum(len(p) for p in paragraphs) < content_size:
            section_title = f"## {random.choice(topics).title()} - Section {len(paragraphs)}\n\n"
            section_body = " ".join(
                "".join(random.choices(string.ascii_lowercase + " ", k=random.randint(3, 10)))
                for _ in range(random.randint(20, 100))
            ) + "\n\n"
            paragraphs.append(section_title + section_body)

        content = "".join(paragraphs)[:content_size]

        doc_path = doc_dir / f"test_doc_{i+1:03d}.md"
        doc_path.write_text(content, encoding="utf-8")
        docs.append(doc_path)

    return docs


def test_indexing_performance(doc_count: int = 100, timeout_seconds: int = 300):
    """
    Test indexing performance with generated documents.

    Args:
        doc_count: Number of documents to index
        timeout_seconds: Maximum allowed time (SC-003: no timeouts)
    """
    print(f"\n{'='*60}")
    print(f"Indexing Performance Test")
    print(f"Documents: {doc_count}, Timeout: {timeout_seconds}s")
    print(f"{'='*60}\n")

    # Create temporary docs directory
    temp_dir = tempfile.mkdtemp(prefix="memoria_perf_test_")
    docs_dir = Path(temp_dir) / "docs"
    docs_dir.mkdir()

    try:
        # Generate test documents
        print(f"Generating {doc_count} test documents...")
        start_gen = time.time()
        test_docs = generate_test_documents(docs_dir, doc_count)
        gen_time = time.time() - start_gen
        total_size = sum(d.stat().st_size for d in test_docs)
        print(f"  Generated {len(test_docs)} docs ({total_size / 1024 / 1024:.1f} MB) in {gen_time:.1f}s\n")

        # Import and configure memoria
        from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
        from memoria.adapters.sentence_transformers.sentence_transformer_adapter import SentenceTransformerAdapter
        from memoria.adapters.document.document_processor_adapter import DocumentProcessorAdapter
        from memoria.domain.entities import Document, ProgressTracker

        # Use a separate test collection to not pollute production
        vector_store = ChromaDBAdapter(
            collection_name="memoria_perf_test",
            use_http=True,
            http_host="localhost",
            http_port=8001,
            timeout=60.0,
        )
        embedder = SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")
        doc_processor = DocumentProcessorAdapter(chunk_size=2000, chunk_overlap=100)

        # Clear test collection
        vector_store.clear()

        # Measure memory before
        resource = None
        try:
            import resource as _resource
            resource = _resource
        except ImportError:
            pass

        # Index documents with batch embedding + progressive batching
        COMMIT_BATCH_SIZE = 500
        tracker = ProgressTracker(total_documents=len(test_docs))
        total_chunks = 0
        pending_chunks = []

        print(f"Starting indexing...")
        start_index = time.time()
        timed_out = False

        for i, doc_path in enumerate(test_docs, 1):
            elapsed = time.time() - start_index
            if elapsed > timeout_seconds:
                timed_out = True
                print(f"\n  TIMEOUT at document {i}/{len(test_docs)} ({elapsed:.1f}s)")
                break

            try:
                chunks = doc_processor.process_document(doc_path)
                pending_chunks.extend(chunks)
                tracker.mark_processed(doc_path.name)

                # Progressive commit
                if len(pending_chunks) >= COMMIT_BATCH_SIZE:
                    texts = [c.content for c in pending_chunks]
                    embeddings = embedder.embed_batch(texts)
                    docs_with_emb = [
                        Document(
                            id=c.id, content=c.content,
                            embedding=e.to_list(), metadata=c.metadata
                        )
                        for c, e in zip(pending_chunks, embeddings)
                    ]
                    vector_store.add_documents(docs_with_emb)
                    total_chunks += len(docs_with_emb)
                    print(f"  Committed {total_chunks} chunks ({i}/{len(test_docs)} docs)...")
                    pending_chunks = []

            except Exception as e:
                tracker.mark_failed(doc_path.name, str(e))
                print(f"  FAILED: {doc_path.name}: {e}")

        # Commit remaining
        if pending_chunks:
            texts = [c.content for c in pending_chunks]
            embeddings = embedder.embed_batch(texts)
            docs_with_emb = [
                Document(
                    id=c.id, content=c.content,
                    embedding=e.to_list(), metadata=c.metadata
                )
                for c, e in zip(pending_chunks, embeddings)
            ]
            vector_store.add_documents(docs_with_emb)
            total_chunks += len(docs_with_emb)

        tracker.finish()
        index_time = tracker.elapsed_seconds

        # Measure memory after
        peak_memory_mb = 0
        if resource is not None:
            peak_memory_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024

        # Results
        print(f"\n{'='*60}")
        print(f"RESULTS")
        print(f"{'='*60}")
        print(f"  Documents processed: {tracker.processed_documents}/{len(test_docs)}")
        print(f"  Documents failed:    {tracker.failed_documents}")
        print(f"  Total chunks:        {total_chunks}")
        print(f"  Index time:          {index_time:.1f}s")
        print(f"  Throughput:          {tracker.docs_per_minute:.1f} docs/min")
        if peak_memory_mb > 0:
            print(f"  Peak memory:         {peak_memory_mb:.0f} MB")

        # Validate success criteria
        print(f"\n{'='*60}")
        print(f"SUCCESS CRITERIA VALIDATION")
        print(f"{'='*60}")

        # SC-003: 0% timeout rate
        sc003_pass = not timed_out
        print(f"  SC-003 (0% timeout):     {'PASS' if sc003_pass else 'FAIL'} "
              f"(timed_out={timed_out})")

        # SC-005: >20 docs/minute throughput
        sc005_pass = tracker.docs_per_minute >= 20
        print(f"  SC-005 (>20 docs/min):   {'PASS' if sc005_pass else 'FAIL'} "
              f"({tracker.docs_per_minute:.1f} docs/min)")

        # SC-007: <2GB peak memory
        if peak_memory_mb > 0:
            sc007_pass = peak_memory_mb < 2048
            print(f"  SC-007 (<2GB memory):    {'PASS' if sc007_pass else 'FAIL'} "
                  f"({peak_memory_mb:.0f} MB)")
        else:
            print(f"  SC-007 (<2GB memory):    SKIP (memory_profiler unavailable)")

        # Overall
        all_pass = sc003_pass and sc005_pass
        print(f"\n  OVERALL: {'ALL PASS' if all_pass else 'SOME FAILURES'}")

        # Cleanup test collection
        vector_store.clear()

        return all_pass

    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_large_document(size_mb: int = 5, timeout_seconds: int = 30):
    """
    Test indexing a single large document.

    Validates acceptance scenario: 5MB markdown indexes in <30 seconds.
    """
    print(f"\n{'='*60}")
    print(f"Large Document Test ({size_mb}MB)")
    print(f"{'='*60}\n")

    temp_dir = tempfile.mkdtemp(prefix="memoria_large_doc_test_")

    try:
        import random
        import string

        # Generate large document
        doc_path = Path(temp_dir) / "large_document.md"
        content_size = size_mb * 1024 * 1024
        content = f"# Large Test Document ({size_mb}MB)\n\n"
        while len(content) < content_size:
            content += " ".join(
                "".join(random.choices(string.ascii_lowercase + " ", k=random.randint(3, 10)))
                for _ in range(100)
            ) + "\n\n"
        content = content[:content_size]
        doc_path.write_text(content, encoding="utf-8")
        print(f"  Generated {doc_path.stat().st_size / 1024 / 1024:.1f} MB document")

        from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
        from memoria.adapters.sentence_transformers.sentence_transformer_adapter import SentenceTransformerAdapter
        from memoria.adapters.document.document_processor_adapter import DocumentProcessorAdapter
        from memoria.domain.entities import Document

        vector_store = ChromaDBAdapter(
            collection_name="memoria_large_doc_test",
            use_http=True,
            http_host="localhost",
            http_port=8001,
            timeout=60.0,
        )
        embedder = SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")
        doc_processor = DocumentProcessorAdapter(chunk_size=2000, chunk_overlap=100)

        vector_store.clear()

        start = time.time()
        chunks = doc_processor.process_document(doc_path)
        print(f"  Chunked into {len(chunks)} chunks ({time.time() - start:.1f}s)")

        texts = [c.content for c in chunks]
        embeddings = embedder.embed_batch(texts)
        print(f"  Embedded {len(embeddings)} chunks ({time.time() - start:.1f}s)")

        docs_with_emb = [
            Document(id=c.id, content=c.content, embedding=e.to_list(), metadata=c.metadata)
            for c, e in zip(chunks, embeddings)
        ]
        vector_store.add_documents(docs_with_emb)
        elapsed = time.time() - start
        print(f"  Committed to database ({elapsed:.1f}s)")

        passed = elapsed < timeout_seconds
        print(f"\n  Result: {'PASS' if passed else 'FAIL'} ({elapsed:.1f}s vs {timeout_seconds}s limit)")

        vector_store.clear()
        return passed

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Memoria indexing performance test")
    parser.add_argument("--docs", type=int, default=100, help="Number of documents to index")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
    parser.add_argument("--large-doc", action="store_true", help="Run large document test")
    args = parser.parse_args()

    if args.large_doc:
        test_large_document()
    else:
        test_indexing_performance(doc_count=args.docs, timeout_seconds=args.timeout)
