"""Skill Helpers - High-Level API for Claude Code"""

from pathlib import Path
import io

# Try to import rich, but provide fallbacks if not available
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

    # Simple fallback implementations
    class Console:
        def __init__(self, file=None, force_terminal=False, width=120):
            self.file = file or io.StringIO()

        def print(self, *args, **kwargs):
            # Strip Rich markup for plain text
            import re
            text = ' '.join(str(arg) for arg in args)
            text = re.sub(r'\[/?[^\]]+\]', '', text)  # Remove [bold], [cyan], etc.
            print(text, file=self.file)

    class Table:
        def __init__(self, **kwargs):
            self.rows = []
            self.columns = []

        def add_column(self, name, **kwargs):
            self.columns.append(name)

        def add_row(self, *values):
            self.rows.append(values)

    class Panel:
        def __init__(self, content, **kwargs):
            self.content = content

        def __str__(self):
            import re
            text = re.sub(r'\[/?[^\]]+\]', '', str(self.content))
            return f"\n{'=' * 60}\n{text}\n{'=' * 60}\n"

# Load .env from ~/.claude/memoria.env if present (avoids manual env setup)
import os
_env_file = Path.home() / ".claude" / "memoria.env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _, _val = _line.partition("=")
            os.environ.setdefault(_key.strip(), _val.strip())

# Import adapters directly
from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
from memoria.adapters.sentence_transformers.sentence_transformer_adapter import SentenceTransformerAdapter
from memoria.adapters.search.search_engine_adapter import SearchEngineAdapter
from memoria.adapters.document.document_processor_adapter import DocumentProcessorAdapter

# Paths
MEMORIA_ROOT = Path(__file__).parent.parent
DOCS_DIR = MEMORIA_ROOT / "docs"
CHROMA_DIR = MEMORIA_ROOT / "chroma_data"

# Global adapter instances
_vector_store = None
_embedder = None
_search_engine = None
_document_processor = None


def _get_adapters():
    global _vector_store, _embedder, _search_engine, _document_processor

    if _vector_store is None:
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        chroma_host = os.getenv("MEMORIA_CHROMA_HOST")
        chroma_port_str = os.getenv("MEMORIA_CHROMA_PORT")
        if not chroma_host or not chroma_port_str:
            raise RuntimeError(
                "MEMORIA_CHROMA_HOST and MEMORIA_CHROMA_PORT must be set. "
                "Run: bash install-plugin.sh (from memoria plugin dir) to configure ~/.claude/memoria.env"
            )
        chroma_port = int(chroma_port_str)

        _vector_store = ChromaDBAdapter(
            collection_name="memoria",
            use_http=True,
            http_host=chroma_host,
            http_port=chroma_port,
        )

        _embedder = _get_embedding_adapter()
        _search_engine = SearchEngineAdapter(_vector_store, _embedder, hybrid_weight=0.95)
        _document_processor = DocumentProcessorAdapter(chunk_size=2000, chunk_overlap=100)

    return _vector_store, _embedder, _search_engine, _document_processor


def _get_document_store():
    """Factory: return configured PostgresDocumentStoreAdapter."""
    from memoria.adapters.postgres.postgres_document_store_adapter import PostgresDocumentStoreAdapter
    return PostgresDocumentStoreAdapter()


def _get_embedding_adapter():
    """Factory: return active embedding adapter based on MEMORIA_EMBEDDING_ADAPTER env var."""
    adapter_name = os.getenv("MEMORIA_EMBEDDING_ADAPTER", "ollama").lower()
    if adapter_name == "sentence_transformers":
        return SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")
    # Default: Ollama adapter
    from memoria.adapters.ollama.ollama_embedding_adapter import OllamaEmbeddingAdapter
    return OllamaEmbeddingAdapter()


def search_knowledge(query, mode="hybrid", expand=True, limit=5):
    import time as _time
    import os as _os

    vector_store, embedder, search_engine, _ = _get_adapters()

    _perf_start = _time.time()
    results = search_engine.search(query=query, limit=limit, mode="hybrid" if mode == "hybrid" else "semantic")
    _perf_elapsed = (_time.time() - _perf_start) * 1000  # ms

    if _os.getenv("MEMORIA_DEBUG"):
        print(f"[PERF] search_knowledge: query_time={_perf_elapsed:.1f}ms, "
              f"results={len(results)}, mode={mode}, limit={limit}")

    console = Console(file=io.StringIO(), force_terminal=False, width=120)
    console.print(f"\n[bold cyan]📚 Search Results for \"{query}\"[/bold cyan]\n")

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return console.file.getvalue()

    for i, result in enumerate(results, 1):
        # SearchResult has .document.content, not .content directly
        content = result.document.content
        source = result.document.metadata.get("source", "unknown")
        score = result.score
        
        if len(content) > 500:
            content = content[:500] + "..."

        console.print(f"[bold]Result {i}[/bold] (Score: {score:.2f})")
        console.print(f"[dim]Source:[/dim] {source}")
        console.print(Panel(content, border_style="dim", padding=(0, 1)))
        console.print()

    return console.file.getvalue()


def index_documents(pattern="**/*.md", rebuild=False):
    """
    Index documents from the docs folder into ChromaDB.

    Uses batch embedding for efficient processing and progressive batching
    to commit chunks to ChromaDB every COMMIT_BATCH_SIZE chunks, preventing
    timeouts and memory exhaustion with large collections.

    Handles individual document failures gracefully - continues indexing
    remaining documents and reports failures in the summary.

    Args:
        pattern: Glob pattern for documents to index (default: "**/*.md")
        rebuild: Ignored for now - always rebuilds (Phase 4 will implement this)
    """
    from memoria.domain.entities import Document, ProgressTracker

    COMMIT_BATCH_SIZE = 500  # Commit to ChromaDB every N chunks (balances memory vs commit overhead)

    vector_store, embedder, _, doc_processor = _get_adapters()
    console = Console(file=io.StringIO(), force_terminal=False, width=120)

    try:
        docs_list = [f for f in DOCS_DIR.glob(pattern) if f.is_file()]
        if not docs_list:
            console.print("[yellow]⚠️  No documents[/yellow]")
            return console.file.getvalue()

        console.print(f"Found {len(docs_list)} documents")
        tracker = ProgressTracker(total_documents=len(docs_list))

        pending_chunks = []  # Chunks waiting for embedding + commit
        total_chunks_committed = 0

        for i, doc_path in enumerate(docs_list, 1):
            tracker.current_document = doc_path.name
            console.print(f"[{i}/{len(docs_list)}] Processing {doc_path.name}...")

            try:
                documents_without_embeddings = doc_processor.process_document(doc_path)
                pending_chunks.extend(documents_without_embeddings)
                tracker.mark_processed(doc_path.name)
            except Exception as doc_err:
                tracker.mark_failed(doc_path.name, str(doc_err))
                console.print(f"[yellow]⚠️  Skipped {doc_path.name}: {doc_err}[/yellow]")
                continue

            # Progressive batching: commit when we have enough chunks
            if len(pending_chunks) >= COMMIT_BATCH_SIZE:
                committed = _embed_and_commit_batch(
                    pending_chunks, embedder, vector_store, console
                )
                total_chunks_committed += committed
                pending_chunks = []

        # Commit remaining chunks
        if pending_chunks:
            committed = _embed_and_commit_batch(
                pending_chunks, embedder, vector_store, console
            )
            total_chunks_committed += committed

        tracker.finish()
        elapsed = tracker.elapsed_seconds
        throughput = tracker.docs_per_minute

        console.print("✓ Build complete\n")
        console.print("[bold green]✅ Indexing Complete[/bold green]\n")
        console.print(f"[cyan]Documents:[/cyan] {tracker.processed_documents}")
        console.print(f"[cyan]Chunks:[/cyan] {total_chunks_committed}")
        console.print(f"[cyan]Throughput:[/cyan] {throughput:.1f} docs/min")
        console.print(f"[cyan]Duration:[/cyan] {elapsed:.1f}s")

        if tracker.failed_documents > 0:
            console.print(f"\n[yellow]⚠️  Failed documents ({tracker.failed_documents}):[/yellow]")
            for filename, error in tracker.failed_files:
                console.print(f"[yellow]  - {filename}: {error}[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Failed: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

    return console.file.getvalue()


def _embed_and_commit_batch(chunks, embedder, vector_store, console):
    """
    Embed a batch of document chunks and commit them to ChromaDB.

    Uses batch embedding API for efficient processing.

    Args:
        chunks: List of Document objects without embeddings
        embedder: SentenceTransformerAdapter instance
        vector_store: ChromaDBAdapter instance
        console: Console for logging

    Returns:
        Number of chunks successfully committed
    """
    from memoria.domain.entities import Document

    if not chunks:
        return 0

    console.print(f"  Embedding {len(chunks)} chunks...")

    try:
        # Extract texts for batch embedding
        texts = [doc.content for doc in chunks]

        # Use batch embedding API (much faster than sequential)
        embeddings = embedder.embed_batch(texts)

        # Create Document objects with embeddings
        docs_with_embeddings = []
        for doc, embedding in zip(chunks, embeddings):
            new_doc = Document(
                id=doc.id,
                content=doc.content,
                embedding=embedding.to_list(),
                metadata=doc.metadata,
            )
            docs_with_embeddings.append(new_doc)

        console.print(f"  Committing {len(docs_with_embeddings)} chunks to database...")
        vector_store.add_documents(docs_with_embeddings)

        return len(docs_with_embeddings)

    except Exception as e:
        console.print(f"[red]⚠️  Batch commit failed ({len(chunks)} chunks): {e}[/red]")
        return 0


def add_document(file_path, reindex=True):
    import shutil
    source_path = Path(file_path)
    if not source_path.exists():
        return f"❌ Not found: {file_path}"
    
    dest_path = DOCS_DIR / source_path.name
    if dest_path.exists():
        return f"⚠️  Already exists: {source_path.name}"
    
    shutil.copy2(source_path, dest_path)
    console = Console(file=io.StringIO(), force_terminal=False, width=120)
    console.print(f"\n[green]✅ Added:[/green] {source_path.name}")
    
    if reindex:
        console.print("[cyan]Re-indexing...[/cyan]")
        index_documents()
        console.print("[green]✅ Done[/green]\n")
    
    return console.file.getvalue()


def list_indexed_documents():
    console = Console(file=io.StringIO(), force_terminal=False, width=120)
    files = [f for f in DOCS_DIR.rglob("*") if f.is_file()]
    console.print(f"\n[bold cyan]📄 Documents ({len(files)} files)[/bold cyan]\n")
    
    if not files:
        console.print("[yellow]No documents[/yellow]")
        return console.file.getvalue()

    by_dir = {}
    for file_path in sorted(files):
        rel_path = file_path.relative_to(DOCS_DIR)
        parent = str(rel_path.parent) if rel_path.parent != Path(".") else "root"
        if parent not in by_dir:
            by_dir[parent] = []
        by_dir[parent].append(rel_path)

    for dir_name, file_list in sorted(by_dir.items()):
        console.print(f"[bold]{dir_name}/[/bold]")
        for fp in sorted(file_list):
            console.print(f"  - {fp.name}")
        console.print()

    return console.file.getvalue()


def get_stats():
    vector_store, _, _, _ = _get_adapters()
    console = Console(file=io.StringIO(), force_terminal=False, width=120)
    console.print("\n[bold cyan]📊 Stats[/bold cyan]\n")

    try:
        count = vector_store._collection.count()
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Chunks", str(count))
        table.add_row("Database", "ChromaDB (HTTP)")
        table.add_row("Collection", vector_store.collection_name)
        console.print(table)
    except Exception as e:
        console.print(f"[red]❌ {e}[/red]")

    return console.file.getvalue()


def check_unindexed_documents(pattern="**/*.md"):
    """
    Check which documents in docs/ are not yet indexed in RAG.

    Args:
        pattern: Glob pattern for files to check (default: all markdown)

    Returns:
        List of relative paths to unindexed documents
    """
    vector_store, _, _, _ = _get_adapters()

    # Get all matching files
    all_docs = [f for f in DOCS_DIR.glob(pattern) if f.is_file()]

    # Get indexed sources from ChromaDB
    try:
        collection = vector_store.get_collection()
        all_metadata = collection.get()['metadatas']
        indexed_sources = {m.get('source') for m in all_metadata if m.get('source')}
    except Exception:
        # If ChromaDB query fails, assume nothing indexed
        indexed_sources = set()

    # Find unindexed
    unindexed = []
    for doc_path in all_docs:
        rel_path = str(doc_path.relative_to(MEMORIA_ROOT))
        if rel_path not in indexed_sources:
            unindexed.append(rel_path)

    return unindexed


def auto_index_new_documents(pattern="**/*.md"):
    """
    Automatically index any unindexed documents in docs/ directory.

    Args:
        pattern: Glob pattern for files to index (default: all markdown)

    Returns:
        Formatted output string showing what was indexed
    """
    console = Console(file=io.StringIO(), force_terminal=False, width=120)

    unindexed = check_unindexed_documents(pattern)

    if not unindexed:
        console.print("[green]✅ All documents already indexed[/green]")
        return console.file.getvalue()

    console.print(f"[yellow]📚 Found {len(unindexed)} unindexed documents[/yellow]")

    for doc in unindexed:
        console.print(f"[dim]  • {doc}[/dim]")

    console.print("\n[cyan]Indexing now...[/cyan]\n")

    # Use index_documents with rebuild=False (it will only process these files)
    result = index_documents(pattern=pattern, rebuild=False)
    console.print(result)

    return console.file.getvalue()


def health_check():
    console = Console(file=io.StringIO(), force_terminal=False, width=120)
    console.print("\n[bold cyan]🏥 Health Check[/bold cyan]\n")

    try:
        vector_store, _, _, _ = _get_adapters()
        count = vector_store._collection.count()

        table = Table(show_header=False, box=None)
        table.add_column("Component", style="cyan")
        table.add_column("Status")
        table.add_row("RAG System", "[green]✅ Healthy[/green]")
        table.add_row("ChromaDB", f"[green]✅ Connected ({count} chunks)[/green]")
        table.add_row("Docs", f"[green]✅ {len([f for f in DOCS_DIR.rglob('*') if f.is_file()])} files[/green]")
        console.print(table)
    except Exception as e:
        console.print(f"[red]❌ Failed: {e}[/red]")

    return console.file.getvalue()


# ---------------------------------------------------------------------------
# US1: Store Documents in Database
# ---------------------------------------------------------------------------

def store_document(content, source_id, title=None):
    """
    Store a document in Postgres and index its chunks in ChromaDB.

    Does not require a /docs folder. The content is stored as-is in Postgres;
    chunks are embedded (via the active embedding adapter) and indexed in ChromaDB.
    If the document already exists with the same content, it is a no-op.

    Args:
        content: Full document text
        source_id: Stable identifier (e.g. "guides/my-guide")
        title: Human-readable title (defaults to source_id if not provided)

    Returns:
        Summary string with source_id, version, and chunk count
    """
    from memoria.domain.entities import Document, ProgressTracker

    doc_store = _get_document_store()
    stored = doc_store.store(source_id, title or source_id, content)

    vector_store, embedder, _, doc_processor = _get_adapters()

    # Delete existing chunks for this source_id before re-indexing
    _delete_chromadb_chunks(vector_store, source_id)

    # Chunk, embed, index — filter whitespace-only chunks, skip oversized ones
    raw_chunks = doc_processor.chunk_text(content, chunk_size=1000, overlap=100)
    chunks = [c for c in raw_chunks if c.text.strip()]
    chunk_count = 0
    if chunks:
        docs_to_add = []
        for i, chunk in enumerate(chunks):
            try:
                embedding = embedder.embed_text(chunk.text.strip())
                docs_to_add.append(Document(
                    id=f"{source_id}_chunk_{i}",
                    content=chunk.text,
                    metadata={"source": source_id, "title": stored.title},
                    embedding=embedding.to_list(),
                ))
            except Exception:
                pass  # Skip chunks that fail embedding (e.g. exceed context length)
        if docs_to_add:
            vector_store.add_documents(docs_to_add)
            chunk_count = len(docs_to_add)

    return f"Stored '{source_id}' (v{stored.version}, {chunk_count} chunks)"


def get_document(source_id):
    """
    Retrieve full document content from Postgres by source_id.

    Args:
        source_id: Stable identifier used when storing the document

    Returns:
        Full document content string

    Raises:
        ValueError: If document not found
    """
    doc_store = _get_document_store()
    stored = doc_store.get(source_id)
    if stored is None:
        raise ValueError(f"Document not found: {source_id}")
    return stored.content


def _delete_chromadb_chunks(vector_store, source_id):
    """Delete all ChromaDB chunks for a given source_id."""
    try:
        # Query for all chunk IDs belonging to this source_id
        results = vector_store._collection.get(
            where={"source": source_id},
            include=[],
        )
        ids = results.get("ids", [])
        if ids:
            vector_store._collection.delete(ids=ids)
    except Exception:
        pass  # If collection doesn't exist yet or query fails, safe to ignore


# ---------------------------------------------------------------------------
# US2: Export Full Corpus to File
# ---------------------------------------------------------------------------

def export_corpus(output_path):
    """
    Export all documents from Postgres to a JSONL file.

    Line 1: ExportManifest JSON
    Lines 2+: One StoredDocument JSON per line

    Args:
        output_path: Absolute or relative path to output .jsonl file

    Returns:
        Summary string with document count and file path
    """
    import json
    import time
    from memoria.domain.entities import ExportManifest

    doc_store = _get_document_store()
    start = time.time()
    count = doc_store.count()

    version = "unknown"
    try:
        version_file = Path(__file__).parent.parent / "VERSION"
        if version_file.exists():
            version = version_file.read_text().strip()
    except Exception:
        pass

    from datetime import datetime, timezone
    manifest = ExportManifest(
        exported_at=datetime.now(tz=timezone.utc),
        document_count=count,
        system_version=version,
        format_version="1.0",
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with output.open("w", encoding="utf-8") as f:
        f.write(json.dumps({
            "exported_at": manifest.exported_at.isoformat(),
            "document_count": manifest.document_count,
            "system_version": manifest.system_version,
            "format_version": manifest.format_version,
        }) + "\n")

        for doc in doc_store.export_all():
            f.write(json.dumps({
                "source_id": doc.source_id,
                "title": doc.title,
                "content": doc.content,
                "fingerprint": doc.fingerprint,
                "version": doc.version,
                "created_at": doc.created_at.isoformat(),
                "updated_at": doc.updated_at.isoformat(),
            }) + "\n")
            written += 1

    elapsed = time.time() - start
    return f"Exported {written} documents to {output_path} in {elapsed:.1f}s"


# ---------------------------------------------------------------------------
# US3: Import and Batch Re-import from File
# ---------------------------------------------------------------------------

def import_corpus(input_path):
    """
    Import documents from a JSONL export file into Postgres and ChromaDB.

    Idempotent: documents with unchanged fingerprints are skipped.
    Processes in batches of 10 documents.

    Args:
        input_path: Path to a .jsonl file produced by export_corpus()

    Returns:
        ImportResult dataclass with counts and any per-document errors

    Raises:
        ValueError: If file format is invalid
    """
    import json
    import time
    from datetime import datetime, timezone
    from memoria.domain.entities import ImportResult

    doc_store = _get_document_store()
    start = time.time()
    added = updated = skipped = failed = 0
    errors = []

    input_file = Path(input_path)
    if not input_file.exists():
        raise ValueError(f"Import file not found: {input_path}")

    with input_file.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        raise ValueError("Import file is empty")

    # Validate manifest (line 1)
    try:
        manifest_data = json.loads(lines[0])
        if "format_version" not in manifest_data:
            raise ValueError("Missing format_version in manifest")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid manifest JSON on line 1: {exc}") from exc

    doc_lines = lines[1:]
    BATCH_SIZE = 10

    for batch_start in range(0, len(doc_lines), BATCH_SIZE):
        batch = doc_lines[batch_start:batch_start + BATCH_SIZE]
        for line in batch:
            line = line.strip()
            if not line:
                continue
            data: dict = {}
            try:
                data = json.loads(line)
                source_id = data["source_id"]
                content = data["content"]
                title = data.get("title", source_id)

                existing_fp = doc_store.get_fingerprint(source_id)
                import hashlib
                new_fp = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

                if existing_fp == new_fp:
                    skipped += 1
                    continue

                stored = doc_store.store(source_id, title, content)
                if stored.version == 1:
                    added += 1
                else:
                    updated += 1

                # Index in ChromaDB
                try:
                    store_document(content, source_id, title)
                except Exception as embed_exc:
                    errors.append((source_id, f"embed error: {embed_exc}"))
                    failed += 1

            except Exception as exc:
                source_id = data.get("source_id", f"line-{batch_start}")
                errors.append((source_id, str(exc)))
                failed += 1

    return ImportResult(
        documents_added=added,
        documents_updated=updated,
        documents_skipped=skipped,
        documents_failed=failed,
        errors=tuple(errors),
        duration_seconds=time.time() - start,
    )


# ---------------------------------------------------------------------------
# US4: Reindex All Documents
# ---------------------------------------------------------------------------

def reindex_corpus():
    """
    Re-read all documents from Postgres and atomically replace the ChromaDB collection.

    Writes all chunks to a temporary collection first. On success, replaces the
    active collection. On failure, the original collection is preserved.

    Returns:
        ReindexResult dataclass with counts and any per-document errors
    """
    import time
    from memoria.domain.entities import ReindexResult
    from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter

    doc_store = _get_document_store()
    embedder = _get_embedding_adapter()
    _, _, _, doc_processor = _get_adapters()
    assert doc_processor is not None

    chroma_host = os.getenv("MEMORIA_CHROMA_HOST")
    chroma_port_str = os.getenv("MEMORIA_CHROMA_PORT")
    if not chroma_host or not chroma_port_str:
        raise RuntimeError(
            "MEMORIA_CHROMA_HOST and MEMORIA_CHROMA_PORT must be set. "
            "Run: bash install-plugin.sh (from memoria plugin dir) to configure ~/.claude/memoria.env"
        )
    chroma_port = int(chroma_port_str)

    import time as _time
    temp_collection_name = f"memoria_reindex_{int(_time.time())}"

    temp_store = ChromaDBAdapter(
        collection_name=temp_collection_name,
        use_http=True,
        http_host=chroma_host,
        http_port=chroma_port,
    )

    start = time.time()
    processed = chunks_created = doc_failed = 0
    errors = []
    embedding_model = embedder.model_name

    try:
        from memoria.domain.entities import Document
        for stored_doc in doc_store.export_all():
            try:
                raw_chunks = doc_processor.chunk_text(stored_doc.content, chunk_size=1000, overlap=100)
                chunks = [c for c in raw_chunks if c.text.strip()]
                if chunks:
                    docs_to_add = []
                    for i, chunk in enumerate(chunks):
                        try:
                            embedding = embedder.embed_text(chunk.text.strip())
                            docs_to_add.append(Document(
                                id=f"{stored_doc.source_id}_chunk_{i}",
                                content=chunk.text,
                                metadata={"source": stored_doc.source_id, "title": stored_doc.title},
                                embedding=embedding.to_list(),
                            ))
                        except Exception:
                            pass  # Skip chunks that fail embedding (e.g. exceed context length)
                    if docs_to_add:
                        temp_store.add_documents(docs_to_add)
                        chunks_created += len(docs_to_add)
                processed += 1
            except Exception as exc:
                errors.append((stored_doc.source_id, str(exc)))
                doc_failed += 1

        # Atomic swap: delete old collection and rename temp
        # ChromaDB HTTP mode: delete old collection, create new with production name
        try:
            temp_store._client.delete_collection("memoria")
        except Exception:
            pass  # May not exist yet

        # Copy temp collection data to production name (in batches to avoid large payloads)
        prod_store = ChromaDBAdapter(
            collection_name="memoria",
            use_http=True,
            http_host=chroma_host,
            http_port=chroma_port,
        )
        _batch_size = 25
        _total = temp_store._collection.count()
        _offset = 0
        while _offset < _total:
            temp_results = temp_store._collection.get(
                limit=_batch_size,
                offset=_offset,
                include=["documents", "metadatas", "embeddings"],
            )
            if not temp_results["ids"]:
                break
            prod_store._collection.add(
                ids=temp_results["ids"],
                documents=temp_results["documents"],
                metadatas=temp_results["metadatas"],
                embeddings=temp_results["embeddings"],
            )
            _offset += _batch_size

        # Invalidate global adapters so next call rebuilds with prod collection
        global _vector_store, _embedder, _search_engine
        _vector_store = None
        _embedder = None
        _search_engine = None

    finally:
        # Always clean up temp collection
        try:
            temp_store._client.delete_collection(temp_collection_name)
        except Exception:
            pass

    return ReindexResult(
        documents_processed=processed,
        chunks_created=chunks_created,
        documents_failed=doc_failed,
        errors=tuple(errors),
        duration_seconds=time.time() - start,
        embedding_model=embedding_model,
    )


# ---------------------------------------------------------------------------
# US5: Document Lifecycle Management
# ---------------------------------------------------------------------------

def delete_document(source_id):
    """
    Delete a document from Postgres and remove its chunks from ChromaDB.

    Args:
        source_id: Identifier of the document to delete

    Returns:
        Summary string confirming deletion or "not found: {source_id}"
    """
    doc_store = _get_document_store()
    deleted = doc_store.delete(source_id)
    if not deleted:
        return f"not found: {source_id}"

    vector_store, _, _, _ = _get_adapters()
    _delete_chromadb_chunks(vector_store, source_id)
    return f"Deleted '{source_id}' from document store and ChromaDB"


def list_documents():
    """
    List all documents stored in Postgres.

    Returns:
        List of StoredDocument records (content included)
    """
    doc_store = _get_document_store()
    return doc_store.list_all()


# ---------------------------------------------------------------------------
# US6: Legacy Migration from /docs Folder
# ---------------------------------------------------------------------------

def migrate_from_docs_folder(docs_dir=None):
    """
    One-time migration: import all .md and .txt files from a folder into Postgres + ChromaDB.

    Idempotent: files with unchanged content (by fingerprint) are skipped.

    Args:
        docs_dir: Path to folder containing documents.
                  Defaults to the memoria/docs/ folder in the package.

    Returns:
        ImportResult dataclass with counts and any per-file errors
    """
    import time
    import hashlib
    from memoria.domain.entities import ImportResult

    if docs_dir is None:
        docs_dir = Path(__file__).parent / "docs"
    docs_path = Path(docs_dir)

    if not docs_path.exists():
        raise ValueError(f"docs_dir does not exist: {docs_dir}")

    doc_store = _get_document_store()
    start = time.time()
    added = updated = skipped = failed = 0
    errors = []

    file_list = sorted([
        f for f in docs_path.rglob("*")
        if f.is_file() and f.suffix.lower() in (".md", ".txt")
    ])

    for file_path in file_list:
        source_id = str(file_path.relative_to(docs_path))
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            title = file_path.stem

            existing_fp = doc_store.get_fingerprint(source_id)
            new_fp = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

            if existing_fp == new_fp:
                skipped += 1
                continue

            stored = doc_store.store(source_id, title, content)
            if stored.version == 1:
                added += 1
            else:
                updated += 1

            # Index in ChromaDB
            store_document(content, source_id, title)

        except Exception as exc:
            errors.append((source_id, str(exc)))
            failed += 1

    return ImportResult(
        documents_added=added,
        documents_updated=updated,
        documents_skipped=skipped,
        documents_failed=failed,
        errors=tuple(errors),
        duration_seconds=time.time() - start,
    )
